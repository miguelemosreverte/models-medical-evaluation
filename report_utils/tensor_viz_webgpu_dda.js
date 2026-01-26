/**
 * WebGPU 3D Tensor Visualization with DDA Voxel Traversal
 * Uses DDA for both rendering AND interaction - "if it renders, it's interactive"
 */

class TensorVisualizationDDA {
    constructor(canvasId, data) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error('Canvas not found:', canvasId);
            return;
        }

        this.data = data;
        this.hoveredCell = null;
        this.selectedCell = null;
        this.tooltipCard = null;
        this.leaderLine = null;

        // Camera settings
        this.cameraDistance = 6;
        this.cameraRotationX = 0.4;
        this.cameraRotationY = 0.6;
        this.isDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;

        // Auto-play feature
        this.autoPlayEnabled = true;
        this.autoPlayIndex = 0;
        this.autoPlayInterval = null;
        this.autoPlayStartTime = Date.now();

        // Voxel grid
        this.voxelGrid = null;
        this.gridBounds = { min: [-2, -2, -1], max: [2, 2, 5] };
        this.voxelSize = 0.1;

        this.init();
    }

    async init() {
        if (!navigator.gpu) {
            console.warn('WebGPU not supported, falling back to Canvas 2D');
            this.fallbackTo2D();
            return;
        }

        try {
            await this.initWebGPU();
        } catch (e) {
            console.warn('WebGPU initialization failed:', e);
            this.fallbackTo2D();
        }
    }

    async initWebGPU() {
        console.log('Initializing WebGPU with DDA...');
        const adapter = await navigator.gpu.requestAdapter();
        if (!adapter) throw new Error('No GPU adapter found');

        const device = await adapter.requestDevice();
        const context = this.canvas.getContext('webgpu');
        const format = navigator.gpu.getPreferredCanvasFormat();

        context.configure({
            device,
            format,
            alphaMode: 'premultiplied'
        });

        this.device = device;
        this.context = context;
        this.format = format;
        console.log('WebGPU initialized successfully');

        this.buildVoxelGrid();
        await this.createPipeline();
        this.setupMouseEvents();
        this.createTooltipCard();
        this.createLeaderLineOverlay();

        // Animation loop
        const animate = () => {
            this.render();
            requestAnimationFrame(animate);
        };
        requestAnimationFrame(animate);

        // Start auto-play after a short delay to avoid initial click events
        setTimeout(() => this.startAutoPlay(), 500);
    }

    buildVoxelGrid() {
        const { codesProcessed } = this.data;
        console.log('Building voxel grid for', codesProcessed, 'codes');

        // Determine which layers to show
        const layersToShow = [];
        if (codesProcessed <= 9) {
            for (let i = 0; i < codesProcessed; i++) layersToShow.push(i);
        } else {
            for (let i = 0; i < 9; i++) layersToShow.push(i);
            layersToShow.push(codesProcessed - 1);
        }

        // Create voxel grid: each cell is a cube
        this.cells = [];
        this.voxelGrid = new Map(); // Map from "x,y,z" to cell data

        layersToShow.forEach((layer, visualIndex) => {
            for (let row = 0; row < 10; row++) {
                for (let col = 0; col < 10; col++) {
                    const x = (col - 4.5) * 0.22;
                    const y = (row - 4.5) * 0.22;
                    const z = visualIndex * 0.35;

                    // WSJ grayscale color
                    const colorFactor = layer / Math.max(codesProcessed - 1, 1);
                    const grayValue = 0.4 + colorFactor * 0.3;

                    const cell = {
                        layer, row, col,
                        x, y, z,
                        visualIndex,
                        color: [grayValue, grayValue, grayValue],
                        size: 0.08
                    };

                    this.cells.push(cell);

                    // Add to voxel grid (discretize position)
                    const voxelKey = this.getVoxelKey(x, y, z);
                    this.voxelGrid.set(voxelKey, cell);
                }
            }
        });

        console.log('Voxel grid built:', this.cells.length, 'cells');

        // Debug: print cube bounds
        if (this.cells.length > 0) {
            const first = this.cells[0];
            const last = this.cells[this.cells.length - 1];
            console.log('First cell:', first.x, first.y, first.z);
            console.log('Last cell:', last.x, last.y, last.z);
        }
    }

    getVoxelKey(x, y, z) {
        const ix = Math.floor(x / this.voxelSize);
        const iy = Math.floor(y / this.voxelSize);
        const iz = Math.floor(z / this.voxelSize);
        return `${ix},${iy},${iz}`;
    }

    async createPipeline() {
        // Standard vertex/fragment pipeline for rendering cubes
        const shaderCode = `
            struct Uniforms {
                projection: mat4x4<f32>,
                view: mat4x4<f32>,
                model: mat4x4<f32>,
            }

            @group(0) @binding(0) var<uniform> uniforms: Uniforms;

            struct VertexInput {
                @location(0) position: vec3<f32>,
                @location(1) color: vec3<f32>,
            }

            struct VertexOutput {
                @builtin(position) position: vec4<f32>,
                @location(0) color: vec3<f32>,
            }

            @vertex
            fn vs_main(input: VertexInput) -> VertexOutput {
                var output: VertexOutput;
                let worldPos = uniforms.model * vec4<f32>(input.position, 1.0);
                let viewPos = uniforms.view * worldPos;
                output.position = uniforms.projection * viewPos;
                output.color = input.color;
                return output;
            }

            @fragment
            fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
                return vec4<f32>(input.color, 1.0);
            }
        `;

        const shaderModule = this.device.createShaderModule({ code: shaderCode });

        this.pipeline = this.device.createRenderPipeline({
            layout: 'auto',
            vertex: {
                module: shaderModule,
                entryPoint: 'vs_main',
                buffers: [{
                    arrayStride: 24,
                    attributes: [
                        { shaderLocation: 0, offset: 0, format: 'float32x3' },
                        { shaderLocation: 1, offset: 12, format: 'float32x3' }
                    ]
                }]
            },
            fragment: {
                module: shaderModule,
                entryPoint: 'fs_main',
                targets: [{ format: this.format }]
            },
            primitive: {
                topology: 'triangle-list',
                cullMode: 'back'
            },
            depthStencil: {
                format: 'depth24plus',
                depthWriteEnabled: true,
                depthCompare: 'less'
            }
        });

        this.createDepthTexture();
        this.createGeometry();
        this.createUniformBuffer();
    }

    createDepthTexture() {
        this.depthTexture = this.device.createTexture({
            size: [this.canvas.width, this.canvas.height],
            format: 'depth24plus',
            usage: GPUTextureUsage.RENDER_ATTACHMENT
        });
    }

    createGeometry() {
        const vertices = [];

        this.cells.forEach(cell => {
            // Check if highlighted
            const isHovered = this.hoveredCell &&
                this.hoveredCell.layer === cell.layer &&
                this.hoveredCell.row === cell.row &&
                this.hoveredCell.col === cell.col;

            const isSelected = this.selectedCell &&
                this.selectedCell.layer === cell.layer &&
                this.selectedCell.row === cell.row &&
                this.selectedCell.col === cell.col;

            const color = (isHovered || isSelected) ? [1.0, 1.0, 1.0] : cell.color;

            this.addCube(vertices, cell.x, cell.y, cell.z, cell.size, color);

            if (isHovered || isSelected) {
                this.addCubeEdges(vertices, cell.x, cell.y, cell.z, cell.size);
            }
        });

        const vertexArray = new Float32Array(vertices);

        this.vertexBuffer = this.device.createBuffer({
            size: vertexArray.byteLength,
            usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST
        });

        this.device.queue.writeBuffer(this.vertexBuffer, 0, vertexArray);
        this.vertexCount = vertices.length / 6;
    }

    addCube(vertices, x, y, z, size, color) {
        const s = size / 2;
        const faces = [
            // Front
            [x-s, y-s, z+s], [x+s, y-s, z+s], [x+s, y+s, z+s],
            [x-s, y-s, z+s], [x+s, y+s, z+s], [x-s, y+s, z+s],
            // Back
            [x-s, y-s, z-s], [x-s, y+s, z-s], [x+s, y+s, z-s],
            [x-s, y-s, z-s], [x+s, y+s, z-s], [x+s, y-s, z-s],
            // Top
            [x-s, y+s, z-s], [x-s, y+s, z+s], [x+s, y+s, z+s],
            [x-s, y+s, z-s], [x+s, y+s, z+s], [x+s, y+s, z-s],
            // Bottom
            [x-s, y-s, z-s], [x+s, y-s, z-s], [x+s, y-s, z+s],
            [x-s, y-s, z-s], [x+s, y-s, z+s], [x-s, y-s, z+s],
            // Right
            [x+s, y-s, z-s], [x+s, y+s, z-s], [x+s, y+s, z+s],
            [x+s, y-s, z-s], [x+s, y+s, z+s], [x+s, y-s, z+s],
            // Left
            [x-s, y-s, z-s], [x-s, y-s, z+s], [x-s, y+s, z+s],
            [x-s, y-s, z-s], [x-s, y+s, z+s], [x-s, y+s, z-s],
        ];

        faces.forEach(v => vertices.push(...v, ...color));
    }

    addCubeEdges(vertices, x, y, z, size) {
        const s = size / 2;
        const t = 0.008;
        const black = [0.0, 0.0, 0.0];

        const edges = [
            [[x-s, y-s, z-s], [x+s, y-s, z-s], t],
            [[x-s, y-s, z+s], [x+s, y-s, z+s], t],
            [[x-s, y-s, z-s], [x-s, y-s, z+s], t],
            [[x+s, y-s, z-s], [x+s, y-s, z+s], t],
            [[x-s, y+s, z-s], [x+s, y+s, z-s], t],
            [[x-s, y+s, z+s], [x+s, y+s, z+s], t],
            [[x-s, y+s, z-s], [x-s, y+s, z+s], t],
            [[x+s, y+s, z-s], [x+s, y+s, z+s], t],
            [[x-s, y-s, z-s], [x-s, y+s, z-s], t],
            [[x+s, y-s, z-s], [x+s, y+s, z-s], t],
            [[x-s, y-s, z+s], [x-s, y+s, z+s], t],
            [[x+s, y-s, z+s], [x+s, y+s, z+s], t],
        ];

        edges.forEach(([p1, p2, thickness]) => {
            vertices.push(...p1, ...black);
            vertices.push(...p2, ...black);
            vertices.push(p2[0], p2[1] + thickness, p2[2], ...black);
            vertices.push(...p1, ...black);
            vertices.push(p2[0], p2[1] + thickness, p2[2], ...black);
            vertices.push(p1[0], p1[1] + thickness, p1[2], ...black);
        });
    }

    createUniformBuffer() {
        const uniformBufferSize = 3 * 16 * 4;
        this.uniformBuffer = this.device.createBuffer({
            size: uniformBufferSize,
            usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST
        });

        this.uniformBindGroup = this.device.createBindGroup({
            layout: this.pipeline.getBindGroupLayout(0),
            entries: [{ binding: 0, resource: { buffer: this.uniformBuffer } }]
        });
    }

    updateUniforms() {
        const projection = this.createPerspectiveMatrix(
            Math.PI / 4,
            this.canvas.width / this.canvas.height,
            0.1,
            100
        );

        const view = this.createViewMatrix();
        const model = this.createIdentityMatrix();

        const uniformData = new Float32Array([...projection, ...view, ...model]);
        this.device.queue.writeBuffer(this.uniformBuffer, 0, uniformData);
    }

    createPerspectiveMatrix(fov, aspect, near, far) {
        const f = 1.0 / Math.tan(fov / 2);
        const rangeInv = 1 / (near - far);

        return [
            f / aspect, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (near + far) * rangeInv, -1,
            0, 0, near * far * rangeInv * 2, 0
        ];
    }

    createViewMatrix() {
        const eye = [
            this.cameraDistance * Math.sin(this.cameraRotationY) * Math.cos(this.cameraRotationX),
            this.cameraDistance * Math.sin(this.cameraRotationX),
            this.cameraDistance * Math.cos(this.cameraRotationY) * Math.cos(this.cameraRotationX)
        ];
        const center = [0, 0, 2];
        const up = [0, 1, 0];

        return this.lookAt(eye, center, up);
    }

    lookAt(eye, center, up) {
        const z = this.normalize([eye[0] - center[0], eye[1] - center[1], eye[2] - center[2]]);
        const x = this.normalize(this.cross(up, z));
        const y = this.cross(z, x);

        return [
            x[0], y[0], z[0], 0,
            x[1], y[1], z[1], 0,
            x[2], y[2], z[2], 0,
            -this.dot(x, eye), -this.dot(y, eye), -this.dot(z, eye), 1
        ];
    }

    normalize(v) {
        const len = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
        return len > 0 ? [v[0] / len, v[1] / len, v[2] / len] : v;
    }

    cross(a, b) {
        return [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]
        ];
    }

    dot(a, b) {
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    }

    createIdentityMatrix() {
        return [
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1
        ];
    }

    // DDA Voxel Traversal for interaction
    ddaRaycast(origin, direction) {
        // DDA algorithm: step through voxels along ray
        let [x, y, z] = origin;
        const [dx, dy, dz] = direction;

        // Normalize direction
        const len = Math.sqrt(dx*dx + dy*dy + dz*dz);
        if (len < 0.0001) {
            console.log('DDA: zero-length direction');
            return null;
        }

        const dirNorm = [dx/len, dy/len, dz/len];
        console.log('DDA ray:', origin, '->', dirNorm);

        // Step size for each axis
        const stepX = Math.sign(dirNorm[0]);
        const stepY = Math.sign(dirNorm[1]);
        const stepZ = Math.sign(dirNorm[2]);

        // tMax: distance to next voxel boundary
        const tDeltaX = Math.abs(this.voxelSize / dirNorm[0]);
        const tDeltaY = Math.abs(this.voxelSize / dirNorm[1]);
        const tDeltaZ = Math.abs(this.voxelSize / dirNorm[2]);

        let tMaxX = tDeltaX * (1 - (x / this.voxelSize) % 1);
        let tMaxY = tDeltaY * (1 - (y / this.voxelSize) % 1);
        let tMaxZ = tDeltaZ * (1 - (z / this.voxelSize) % 1);

        // Maximum steps to prevent infinite loop
        const maxSteps = 100;
        let checksCount = 0;
        let cellsFound = 0;

        for (let step = 0; step < maxSteps; step++) {
            checksCount++;

            // Check current voxel
            const key = this.getVoxelKey(x, y, z);
            const cell = this.voxelGrid.get(key);

            if (cell) {
                cellsFound++;
                // Hit! Check if actually inside cube bounds
                const s = cell.size / 2;
                if (x >= cell.x - s && x <= cell.x + s &&
                    y >= cell.y - s && y <= cell.y + s &&
                    z >= cell.z - s && z <= cell.z + s) {
                    console.log('DDA hit after', checksCount, 'checks, found', cellsFound, 'candidates');
                    return cell;
                }
            }

            // Step to next voxel
            if (tMaxX < tMaxY) {
                if (tMaxX < tMaxZ) {
                    x += stepX * this.voxelSize;
                    tMaxX += tDeltaX;
                } else {
                    z += stepZ * this.voxelSize;
                    tMaxZ += tDeltaZ;
                }
            } else {
                if (tMaxY < tMaxZ) {
                    y += stepY * this.voxelSize;
                    tMaxY += tDeltaY;
                } else {
                    z += stepZ * this.voxelSize;
                    tMaxZ += tDeltaZ;
                }
            }

            // Check bounds
            if (x < this.gridBounds.min[0] || x > this.gridBounds.max[0] ||
                y < this.gridBounds.min[1] || y > this.gridBounds.max[1] ||
                z < this.gridBounds.min[2] || z > this.gridBounds.max[2]) {
                break;
            }
        }

        console.log('DDA miss after', checksCount, 'checks, found', cellsFound, 'candidates');
        return null;
    }

    getRayFromMouse(mouseX, mouseY) {
        const ndc = {
            x: (mouseX / this.canvas.width) * 2 - 1,
            y: 1 - (mouseY / this.canvas.height) * 2
        };

        const eye = [
            this.cameraDistance * Math.sin(this.cameraRotationY) * Math.cos(this.cameraRotationX),
            this.cameraDistance * Math.sin(this.cameraRotationX),
            this.cameraDistance * Math.cos(this.cameraRotationY) * Math.cos(this.cameraRotationX)
        ];

        const view = this.createViewMatrix();
        const projection = this.createPerspectiveMatrix(
            Math.PI / 4,
            this.canvas.width / this.canvas.height,
            0.1,
            100
        );

        const invProjection = this.invertMatrix(projection);
        const invView = this.invertMatrix(view);

        let rayClip = [ndc.x, ndc.y, -1, 1];
        let rayView = this.multiplyMatrixVector(invProjection, rayClip);
        rayView = [rayView[0], rayView[1], -1, 0];

        let rayWorld = this.multiplyMatrixVector(invView, rayView);
        const dir = this.normalize([rayWorld[0], rayWorld[1], rayWorld[2]]);

        const center = [0, 0, 2];
        const origin = [
            eye[0] + center[0],
            eye[1] + center[1],
            eye[2] + center[2]
        ];

        return { origin, direction: dir };
    }

    multiplyMatrixVector(matrix, vector) {
        const result = [0, 0, 0, 0];
        for (let i = 0; i < 4; i++) {
            for (let j = 0; j < 4; j++) {
                result[i] += matrix[i * 4 + j] * vector[j];
            }
        }
        return result;
    }

    invertMatrix(m) {
        const inv = new Array(16);

        inv[0] = m[5] * m[10] * m[15] - m[5] * m[11] * m[14] - m[9] * m[6] * m[15] +
                 m[9] * m[7] * m[14] + m[13] * m[6] * m[11] - m[13] * m[7] * m[10];
        inv[4] = -m[4] * m[10] * m[15] + m[4] * m[11] * m[14] + m[8] * m[6] * m[15] -
                 m[8] * m[7] * m[14] - m[12] * m[6] * m[11] + m[12] * m[7] * m[10];
        inv[8] = m[4] * m[9] * m[15] - m[4] * m[11] * m[13] - m[8] * m[5] * m[15] +
                 m[8] * m[7] * m[13] + m[12] * m[5] * m[11] - m[12] * m[7] * m[9];
        inv[12] = -m[4] * m[9] * m[14] + m[4] * m[10] * m[13] + m[8] * m[5] * m[14] -
                  m[8] * m[6] * m[13] - m[12] * m[5] * m[10] + m[12] * m[6] * m[9];
        inv[1] = -m[1] * m[10] * m[15] + m[1] * m[11] * m[14] + m[9] * m[2] * m[15] -
                 m[9] * m[3] * m[14] - m[13] * m[2] * m[11] + m[13] * m[3] * m[10];
        inv[5] = m[0] * m[10] * m[15] - m[0] * m[11] * m[14] - m[8] * m[2] * m[15] +
                 m[8] * m[3] * m[14] + m[12] * m[2] * m[11] - m[12] * m[3] * m[10];
        inv[9] = -m[0] * m[9] * m[15] + m[0] * m[11] * m[13] + m[8] * m[1] * m[15] -
                 m[8] * m[3] * m[13] - m[12] * m[1] * m[11] + m[12] * m[3] * m[9];
        inv[13] = m[0] * m[9] * m[14] - m[0] * m[10] * m[13] - m[8] * m[1] * m[14] +
                  m[8] * m[2] * m[13] + m[12] * m[1] * m[10] - m[12] * m[2] * m[9];
        inv[2] = m[1] * m[6] * m[15] - m[1] * m[7] * m[14] - m[5] * m[2] * m[15] +
                 m[5] * m[3] * m[14] + m[13] * m[2] * m[7] - m[13] * m[3] * m[6];
        inv[6] = -m[0] * m[6] * m[15] + m[0] * m[7] * m[14] + m[4] * m[2] * m[15] -
                 m[4] * m[3] * m[14] - m[12] * m[2] * m[7] + m[12] * m[3] * m[6];
        inv[10] = m[0] * m[5] * m[15] - m[0] * m[7] * m[13] - m[4] * m[1] * m[15] +
                  m[4] * m[3] * m[13] + m[12] * m[1] * m[7] - m[12] * m[3] * m[5];
        inv[14] = -m[0] * m[5] * m[14] + m[0] * m[6] * m[13] + m[4] * m[1] * m[14] -
                  m[4] * m[2] * m[13] - m[12] * m[1] * m[6] + m[12] * m[2] * m[5];
        inv[3] = -m[1] * m[6] * m[11] + m[1] * m[7] * m[10] + m[5] * m[2] * m[11] -
                 m[5] * m[3] * m[10] - m[9] * m[2] * m[7] + m[9] * m[3] * m[6];
        inv[7] = m[0] * m[6] * m[11] - m[0] * m[7] * m[10] - m[4] * m[2] * m[11] +
                 m[4] * m[3] * m[10] + m[8] * m[2] * m[7] - m[8] * m[3] * m[6];
        inv[11] = -m[0] * m[5] * m[11] + m[0] * m[7] * m[9] + m[4] * m[1] * m[11] -
                  m[4] * m[3] * m[9] - m[8] * m[1] * m[7] + m[8] * m[3] * m[5];
        inv[15] = m[0] * m[5] * m[10] - m[0] * m[6] * m[9] - m[4] * m[1] * m[10] +
                  m[4] * m[2] * m[9] + m[8] * m[1] * m[6] - m[8] * m[2] * m[5];

        let det = m[0] * inv[0] + m[1] * inv[4] + m[2] * inv[8] + m[3] * inv[12];

        if (Math.abs(det) < 0.0001) {
            return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
        }

        det = 1.0 / det;
        for (let i = 0; i < 16; i++) {
            inv[i] *= det;
        }

        return inv;
    }

    setupMouseEvents() {
        this.canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.lastMouseX = e.clientX;
            this.lastMouseY = e.clientY;
        });

        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                const deltaX = e.clientX - this.lastMouseX;
                const deltaY = e.clientY - this.lastMouseY;

                this.cameraRotationY += deltaX * 0.01;
                this.cameraRotationX += deltaY * 0.01;
                this.cameraRotationX = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, this.cameraRotationX));

                this.lastMouseX = e.clientX;
                this.lastMouseY = e.clientY;
            } else {
                this.checkHover(e);
            }
        });

        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            this.hoveredCell = null;
            if (!this.selectedCell) {
                this.hideTooltip();
            }
            this.createGeometry(); // Rebuild to remove hover highlight
        });

        this.canvas.addEventListener('click', (e) => {
            const timeSinceStart = Date.now() - this.autoPlayStartTime;
            console.log('Click event, time since auto-play start:', timeSinceStart, 'ms');

            // Only stop auto-play if it's been running for at least 1 second
            if (timeSinceStart > 1000) {
                console.log('Stopping auto-play due to user click');
                this.stopAutoPlay();
            } else {
                console.log('Ignoring click - too soon after auto-play start');
            }

            if (this.hoveredCell) {
                console.log('Selecting cell:', this.hoveredCell);
                this.selectedCell = this.hoveredCell;
                this.showTooltip(this.selectedCell, e, true);
                this.createGeometry();
            } else {
                console.log('Deselecting cell');
                this.selectedCell = null;
                this.hideTooltip();
                this.createGeometry();
            }
        });

        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.cameraDistance += e.deltaY * 0.01;
            this.cameraDistance = Math.max(3, Math.min(15, this.cameraDistance));
        });
    }

    checkHover(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Use DDA raycast for interaction
        const ray = this.getRayFromMouse(mouseX, mouseY);
        const hitCell = this.ddaRaycast(ray.origin, ray.direction);

        if (hitCell !== this.hoveredCell) {
            if (hitCell) {
                console.log('DDA hit cell:', hitCell.layer, hitCell.row, hitCell.col);
            }
            this.hoveredCell = hitCell;
            if (hitCell && !this.selectedCell) {
                this.showTooltip(hitCell, e, false);
            }
            this.createGeometry(); // Rebuild geometry with new hover state
        }
    }

    startAutoPlay() {
        if (!this.cells || this.cells.length === 0) return;

        console.log('Starting auto-play with', this.cells.length, 'cells');
        this.autoPlayStartTime = Date.now();

        this.autoPlayInterval = setInterval(() => {
            if (!this.autoPlayEnabled) return;

            const cell = this.cells[this.autoPlayIndex];

            // Project cell to screen coordinates
            const projected = this.project3DTo2D(cell.x, cell.y, cell.z);
            if (projected) {
                const fakeEvent = {
                    clientX: projected.x + this.canvas.getBoundingClientRect().left,
                    clientY: projected.y + this.canvas.getBoundingClientRect().top
                };

                this.selectedCell = cell;
                this.showTooltip(cell, fakeEvent, true);
                this.createGeometry();
            }

            this.autoPlayIndex = (this.autoPlayIndex + 1) % this.cells.length;
        }, 2000);
    }

    stopAutoPlay() {
        if (this.autoPlayInterval) {
            console.log('Stopping auto-play');
            this.autoPlayEnabled = false;
            clearInterval(this.autoPlayInterval);
            this.autoPlayInterval = null;
        }
    }

    project3DTo2D(x, y, z) {
        const view = this.createViewMatrix();
        const projection = this.createPerspectiveMatrix(
            Math.PI / 4,
            this.canvas.width / this.canvas.height,
            0.1,
            100
        );

        let point = [x, y, z, 1];
        point = this.multiplyMatrixVector(view, point);
        point = this.multiplyMatrixVector(projection, point);

        if (point[3] <= 0) return null;

        const screenX = (point[0] / point[3] + 1) * 0.5 * this.canvas.width;
        const screenY = (1 - point[1] / point[3]) * 0.5 * this.canvas.height;

        return { x: screenX, y: screenY };
    }

    createTooltipCard() {
        this.tooltipCard = document.createElement('div');
        this.tooltipCard.style.cssText = `
            position: fixed;
            background: white;
            border: 2px solid #000;
            border-radius: 4px;
            padding: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-size: 13px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            z-index: 1000;
            min-width: 240px;
            font-family: Georgia, 'Times New Roman', serif;
        `;
        document.body.appendChild(this.tooltipCard);
    }

    createLeaderLineOverlay() {
        this.leaderLine = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        this.leaderLine.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 999;
        `;
        document.body.appendChild(this.leaderLine);
    }

    showTooltip(cell, event, isClick) {
        const { layer, row, col } = cell;
        const variantType = col < 5 ? 'Short' : 'Long';
        const variantIndex = (col % 5) + 1;

        this.tooltipCard.innerHTML = `
            <div style="font-weight: 700; margin-bottom: 12px; color: #000; font-size: 15px; border-bottom: 2px solid #000; padding-bottom: 8px;">
                Code Layer ${layer + 1}
            </div>
            <div style="margin-bottom: 6px; color: #333;">
                <strong>Variant Type:</strong> ${variantType}
            </div>
            <div style="margin-bottom: 6px; color: #333;">
                <strong>Variant Index:</strong> ${variantIndex}
            </div>
            <div style="margin-bottom: 6px; color: #333;">
                <strong>Row:</strong> ${row + 1}
            </div>
            <div style="margin-bottom: 6px; color: #333;">
                <strong>Column:</strong> ${col + 1}
            </div>
            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #ccc; font-size: 11px; color: #666;">
                Matrix Position: [${row + 1}, ${col + 1}] in Layer ${layer + 1}/${this.data.codesProcessed}
            </div>
        `;

        const rect = this.canvas.getBoundingClientRect();

        const canvasEdgeX = event.clientX > rect.left + rect.width / 2 ? rect.right : rect.left;
        const canvasEdgeY = event.clientY > rect.top + rect.height / 2 ? rect.bottom : rect.top;

        const distance = Math.min(
            Math.abs(canvasEdgeX - event.clientX),
            Math.abs(canvasEdgeY - event.clientY)
        );

        const direction = {
            x: event.clientX > rect.left + rect.width / 2 ? 1 : -1,
            y: event.clientY > rect.top + rect.height / 2 ? 1 : -1
        };

        const diagonalEndX = event.clientX + direction.x * distance;
        const diagonalEndY = event.clientY + direction.y * distance;

        const tooltipX = diagonalEndX + direction.x * 20;
        const tooltipY = diagonalEndY + direction.y * 20;

        this.tooltipCard.style.left = tooltipX + 'px';
        this.tooltipCard.style.top = tooltipY + 'px';
        this.tooltipCard.style.opacity = '1';

        if (isClick) {
            this.drawLeaderLine(event.clientX, event.clientY, diagonalEndX, diagonalEndY, tooltipX, tooltipY);
        } else {
            this.leaderLine.innerHTML = '';
        }
    }

    hideTooltip() {
        this.tooltipCard.style.opacity = '0';
        this.leaderLine.innerHTML = '';
    }

    drawLeaderLine(startX, startY, diagonalEndX, diagonalEndY, tooltipX, tooltipY) {
        this.leaderLine.innerHTML = `
            <line x1="${startX}" y1="${startY}" x2="${diagonalEndX}" y2="${diagonalEndY}" stroke="#000" stroke-width="2" />
            <line x1="${diagonalEndX}" y1="${diagonalEndY}" x2="${tooltipX}" y2="${tooltipY}" stroke="#000" stroke-width="1" />
            <circle cx="${startX}" cy="${startY}" r="5" fill="#000" />
            <circle cx="${tooltipX}" cy="${tooltipY}" r="3" fill="#000" />
        `;
    }

    render() {
        if (!this.device) return;

        this.updateUniforms();

        const commandEncoder = this.device.createCommandEncoder();
        const textureView = this.context.getCurrentTexture().createView();

        const renderPassDescriptor = {
            colorAttachments: [{
                view: textureView,
                clearValue: { r: 1.0, g: 1.0, b: 1.0, a: 0.0 },
                loadOp: 'clear',
                storeOp: 'store'
            }],
            depthStencilAttachment: {
                view: this.depthTexture.createView(),
                depthClearValue: 1.0,
                depthLoadOp: 'clear',
                depthStoreOp: 'store'
            }
        };

        const passEncoder = commandEncoder.beginRenderPass(renderPassDescriptor);
        passEncoder.setPipeline(this.pipeline);
        passEncoder.setBindGroup(0, this.uniformBindGroup);
        passEncoder.setVertexBuffer(0, this.vertexBuffer);
        passEncoder.draw(this.vertexCount);
        passEncoder.end();

        this.device.queue.submit([commandEncoder.finish()]);
    }

    fallbackTo2D() {
        const ctx = this.canvas.getContext('2d');
        const { codesProcessed, totalCodes } = this.data;

        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.fillStyle = '#333';
        ctx.font = 'bold 16px Georgia, serif';
        ctx.textAlign = 'center';
        ctx.fillText('3D Tensor Visualization', this.canvas.width / 2, 30);
        ctx.font = '14px Georgia, serif';
        ctx.fillText(`${codesProcessed} / ${totalCodes} codes processed`, this.canvas.width / 2, 60);
        ctx.fillText('(WebGPU not available)', this.canvas.width / 2, 85);
    }
}

function initTensorVisualization(canvasId, data) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new TensorVisualizationDDA(canvasId, data);
        });
    } else {
        new TensorVisualizationDDA(canvasId, data);
    }
}
