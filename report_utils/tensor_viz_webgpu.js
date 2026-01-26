/**
 * WebGPU 3D Tensor Visualization with Interactive Tooltips
 * Visualizes the 10×10×N variant tensor with hover cards and leader lines
 */

class TensorVisualization {
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

        this.init();
    }

    async init() {
        // Check WebGPU support
        if (!navigator.gpu) {
            console.warn('WebGPU not supported, falling back to Canvas 2D');
            this.fallbackTo2D();
            return;
        }

        try {
            await this.initWebGPU();
        } catch (e) {
            console.warn('WebGPU initialization failed, falling back to Canvas 2D:', e);
            this.fallbackTo2D();
        }
    }

    async initWebGPU() {
        console.log('Initializing WebGPU...');
        const adapter = await navigator.gpu.requestAdapter();
        if (!adapter) {
            console.error('No GPU adapter found');
            throw new Error('No GPU adapter found');
        }

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

        await this.createPipeline();
        this.createDepthTexture();
        this.setupMouseEvents();
        this.createTooltipCard();
        this.createLeaderLineOverlay();
        this.render();

        // Animation loop for smooth interaction
        const animate = () => {
            this.render();
            requestAnimationFrame(animate);
        };
        requestAnimationFrame(animate);

        // Start auto-play
        this.startAutoPlay();
    }

    createDepthTexture() {
        this.depthTexture = this.device.createTexture({
            size: [this.canvas.width, this.canvas.height],
            format: 'depth24plus',
            usage: GPUTextureUsage.RENDER_ATTACHMENT
        });
    }

    async createPipeline() {
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
                    arrayStride: 24, // 6 floats * 4 bytes
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

        this.createGeometry();
        this.createUniformBuffer();
        this.needsGeometryRebuild = false;
    }

    createGeometry() {
        if (!this.device) return;
        const vertices = [];
        const { codesProcessed, totalCodes } = this.data;

        console.log('Creating geometry for', codesProcessed, 'codes');

        // Show layers 1-9, then ellipsis, then last
        const layersToShow = [];

        if (codesProcessed <= 9) {
            // Just show what we have (1-N)
            for (let i = 0; i < codesProcessed; i++) {
                layersToShow.push(i);
            }
        } else {
            // Show 1-9
            for (let i = 0; i < 9; i++) {
                layersToShow.push(i);
            }
            // Then show the last layer
            layersToShow.push(codesProcessed - 1);
        }

        console.log('Layers to show:', layersToShow);

        // Create cells for visible layers
        this.cells = [];

        layersToShow.forEach((layer, visualIndex) => {
            for (let row = 0; row < 10; row++) {
                for (let col = 0; col < 10; col++) {
                    const x = (col - 4.5) * 0.22;
                    const y = (row - 4.5) * 0.22;
                    const z = visualIndex * 0.35;

                    // WSJ style: grayscale gradient based on layer
                    const colorFactor = layer / Math.max(codesProcessed - 1, 1);
                    const grayValue = 0.4 + colorFactor * 0.3;  // 0.4 to 0.7 (medium to light gray)
                    const color = [grayValue, grayValue, grayValue];

                    // Check hover/selected by matching properties, not reference
                    const isHovered = this.hoveredCell &&
                        this.hoveredCell.layer === layer &&
                        this.hoveredCell.row === row &&
                        this.hoveredCell.col === col;

                    const isSelected = this.selectedCell &&
                        this.selectedCell.layer === layer &&
                        this.selectedCell.row === row &&
                        this.selectedCell.col === col;

                    if (isHovered || isSelected) {
                        console.log('Highlighting cell at layer', layer, 'row', row, 'col', col, 'hovered:', isHovered, 'selected:', isSelected);
                    }

                    // Highlight: white for hovered/selected
                    const finalColor = (isHovered || isSelected) ?
                        [1.0, 1.0, 1.0] : color;

                    this.addCube(vertices, x, y, z, 0.08, finalColor);

                    // Add black edges for hovered/selected cubes
                    if (isHovered || isSelected) {
                        this.addCubeEdges(vertices, x, y, z, 0.08);
                    }

                    this.cells.push({ layer, row, col, x, y, z, visualIndex });
                }
            }
        });

        // Add ellipsis indicator if needed (WSJ gray)
        if (codesProcessed > 9) {
            const ellipsisZ = 9 * 0.35 + 0.175; // Between layer 9 and last
            for (let i = 0; i < 3; i++) {
                const x = (i - 1) * 0.15;
                this.addCube(vertices, x, 0, ellipsisZ, 0.06, [0.6, 0.6, 0.6]);
            }
        }

        const vertexArray = new Float32Array(vertices);

        this.vertexBuffer = this.device.createBuffer({
            size: vertexArray.byteLength,
            usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST
        });

        this.device.queue.writeBuffer(this.vertexBuffer, 0, vertexArray);
        this.vertexCount = vertices.length / 6;

        console.log('Geometry created:', this.cells.length, 'cells,', this.vertexCount, 'vertices');
        console.log('Hover state:', this.hoveredCell, 'Selected:', this.selectedCell);
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

        faces.forEach(v => {
            vertices.push(...v, ...color);
        });
    }

    addCubeEdges(vertices, x, y, z, size) {
        // Add thin black border strips along cube edges
        const s = size / 2;
        const edgeThickness = 0.008;
        const black = [0.0, 0.0, 0.0];

        // Create thin rectangular strips for each edge
        const edges = [
            // Bottom square edges
            [[x-s, y-s, z-s], [x+s, y-s, z-s], edgeThickness],  // bottom front
            [[x-s, y-s, z+s], [x+s, y-s, z+s], edgeThickness],  // bottom back
            [[x-s, y-s, z-s], [x-s, y-s, z+s], edgeThickness],  // bottom left
            [[x+s, y-s, z-s], [x+s, y-s, z+s], edgeThickness],  // bottom right

            // Top square edges
            [[x-s, y+s, z-s], [x+s, y+s, z-s], edgeThickness],  // top front
            [[x-s, y+s, z+s], [x+s, y+s, z+s], edgeThickness],  // top back
            [[x-s, y+s, z-s], [x-s, y+s, z+s], edgeThickness],  // top left
            [[x+s, y+s, z-s], [x+s, y+s, z+s], edgeThickness],  // top right

            // Vertical edges
            [[x-s, y-s, z-s], [x-s, y+s, z-s], edgeThickness],  // front left
            [[x+s, y-s, z-s], [x+s, y+s, z-s], edgeThickness],  // front right
            [[x-s, y-s, z+s], [x-s, y+s, z+s], edgeThickness],  // back left
            [[x+s, y-s, z+s], [x+s, y+s, z+s], edgeThickness],  // back right
        ];

        // For each edge, create a small quad
        edges.forEach(([p1, p2, thickness]) => {
            const t = thickness;
            // Simple edge representation
            vertices.push(...p1, ...black);
            vertices.push(...p2, ...black);
            vertices.push(p2[0], p2[1] + t, p2[2], ...black);

            vertices.push(...p1, ...black);
            vertices.push(p2[0], p2[1] + t, p2[2], ...black);
            vertices.push(p1[0], p1[1] + t, p1[2], ...black);
        });
    }

    createUniformBuffer() {
        const uniformBufferSize = 3 * 16 * 4; // 3 mat4x4, each 16 floats of 4 bytes
        this.uniformBuffer = this.device.createBuffer({
            size: uniformBufferSize,
            usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST
        });

        this.uniformBindGroup = this.device.createBindGroup({
            layout: this.pipeline.getBindGroupLayout(0),
            entries: [{
                binding: 0,
                resource: { buffer: this.uniformBuffer }
            }]
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

        const uniformData = new Float32Array([
            ...projection,
            ...view,
            ...model
        ]);

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
        return [v[0] / len, v[1] / len, v[2] / len];
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

    setupMouseEvents() {
        this.canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.lastMouseX = e.clientX;
            this.lastMouseY = e.clientY;
        });

        this.lastHoverX = -1;
        this.lastHoverY = -1;

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
                // Only check hover if mouse actually moved
                const rect = this.canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;

                if (Math.abs(mouseX - this.lastHoverX) > 1 || Math.abs(mouseY - this.lastHoverY) > 1) {
                    this.lastHoverX = mouseX;
                    this.lastHoverY = mouseY;
                    this.checkHover(e);
                }
            }
        });

        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            this.hideTooltip();
        });

        this.canvas.addEventListener('click', (e) => {
            // Stop auto-play on user interaction
            this.stopAutoPlay();

            if (this.hoveredCell) {
                console.log('Clicking cell:', this.hoveredCell);
                this.selectedCell = this.hoveredCell;
                this.showTooltip(this.selectedCell, e, true);
                this.needsGeometryRebuild = true; // Flag for rebuild
            } else {
                // Click on empty space deselects
                this.selectedCell = null;
                this.hideTooltip();
                this.needsGeometryRebuild = true;
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

        // Use ray casting to find intersected cube
        const ray = this.getRayFromMouse(mouseX, mouseY);
        const hitCell = this.raycastCubes(ray);

        if (hitCell && hitCell !== this.hoveredCell) {
            console.log('Hovering cell:', hitCell);
            this.hoveredCell = hitCell;
            this.showTooltip(hitCell, e, false);
            this.needsGeometryRebuild = true;
        } else if (!hitCell && this.hoveredCell) {
            this.hoveredCell = null;
            if (!this.selectedCell) {
                this.hideTooltip();
            }
            this.needsGeometryRebuild = true;
        }
    }

    getRayFromMouse(mouseX, mouseY) {
        // Convert mouse coordinates to normalized device coordinates (-1 to 1)
        const ndc = {
            x: (mouseX / this.canvas.width) * 2 - 1,
            y: 1 - (mouseY / this.canvas.height) * 2
        };

        // Get camera position
        const eye = [
            this.cameraDistance * Math.sin(this.cameraRotationY) * Math.cos(this.cameraRotationX),
            this.cameraDistance * Math.sin(this.cameraRotationX),
            this.cameraDistance * Math.cos(this.cameraRotationY) * Math.cos(this.cameraRotationX)
        ];

        // Get view and projection matrices
        const view = this.createViewMatrix();
        const projection = this.createPerspectiveMatrix(
            Math.PI / 4,
            this.canvas.width / this.canvas.height,
            0.1,
            100
        );

        // Inverse projection to get ray in view space
        const invProjection = this.invertMatrix(projection);
        const invView = this.invertMatrix(view);

        // Ray in clip space
        let rayClip = [ndc.x, ndc.y, -1, 1];

        // Ray in view space
        let rayView = this.multiplyMatrixVector(invProjection, rayClip);
        rayView = [rayView[0], rayView[1], -1, 0]; // Point forward

        // Ray in world space
        let rayWorld = this.multiplyMatrixVector(invView, rayView);

        // Normalize direction
        const dir = this.normalize([rayWorld[0], rayWorld[1], rayWorld[2]]);

        // Adjust origin to account for center offset
        const center = [0, 0, 2];
        const origin = [
            eye[0] + center[0],
            eye[1] + center[1],
            eye[2] + center[2]
        ];

        return { origin, direction: dir };
    }

    raycastCubes(ray) {
        let closestCell = null;
        let minDistance = Infinity;

        // Check each cube for intersection
        this.cells.forEach(cell => {
            const cubeSize = 0.08;
            const bounds = {
                min: [cell.x - cubeSize/2, cell.y - cubeSize/2, cell.z - cubeSize/2],
                max: [cell.x + cubeSize/2, cell.y + cubeSize/2, cell.z + cubeSize/2]
            };

            const distance = this.rayBoxIntersection(ray, bounds);
            if (distance !== null && distance < minDistance) {
                minDistance = distance;
                closestCell = cell;
            }
        });

        return closestCell;
    }

    rayBoxIntersection(ray, bounds) {
        // Slab method for ray-AABB intersection
        let tmin = -Infinity;
        let tmax = Infinity;

        for (let i = 0; i < 3; i++) {
            if (Math.abs(ray.direction[i]) < 0.0001) {
                // Ray is parallel to slab
                if (ray.origin[i] < bounds.min[i] || ray.origin[i] > bounds.max[i]) {
                    return null; // No intersection
                }
            } else {
                const t1 = (bounds.min[i] - ray.origin[i]) / ray.direction[i];
                const t2 = (bounds.max[i] - ray.origin[i]) / ray.direction[i];

                const tNear = Math.min(t1, t2);
                const tFar = Math.max(t1, t2);

                tmin = Math.max(tmin, tNear);
                tmax = Math.min(tmax, tFar);

                if (tmin > tmax) return null; // No intersection
            }
        }

        if (tmax < 0) return null; // Box is behind ray

        return tmin > 0 ? tmin : tmax; // Return closest positive intersection
    }

    invertMatrix(m) {
        // 4x4 matrix inversion (simplified for our use case)
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
            // Return identity matrix if not invertible
            return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
        }

        det = 1.0 / det;
        for (let i = 0; i < 16; i++) {
            inv[i] *= det;
        }

        return inv;
    }

    startAutoPlay() {
        if (!this.cells || this.cells.length === 0) return;

        console.log('Starting auto-play with', this.cells.length, 'cells');

        this.autoPlayInterval = setInterval(() => {
            if (!this.autoPlayEnabled) return;

            const cell = this.cells[this.autoPlayIndex];

            // Simulate a click event at the cell's projected position
            const projected = this.project3DTo2D(cell.x, cell.y, cell.z);
            if (projected) {
                const fakeEvent = {
                    clientX: projected.x + this.canvas.getBoundingClientRect().left,
                    clientY: projected.y + this.canvas.getBoundingClientRect().top
                };

                this.selectedCell = cell;
                this.hoveredCell = cell;
                this.showTooltip(cell, fakeEvent, true);
                this.needsGeometryRebuild = true;
            }

            // Move to next cell
            this.autoPlayIndex = (this.autoPlayIndex + 1) % this.cells.length;
        }, 2000); // 2 seconds per cell
    }

    stopAutoPlay() {
        if (this.autoPlayInterval) {
            console.log('Stopping auto-play from:', new Error().stack);
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

        // Transform point through view and projection
        let point = [x, y, z, 1];

        // Apply view matrix
        point = this.multiplyMatrixVector(view, point);
        // Apply projection matrix
        point = this.multiplyMatrixVector(projection, point);

        if (point[3] <= 0) return null;

        // Perspective divide
        const screenX = (point[0] / point[3] + 1) * 0.5 * this.canvas.width;
        const screenY = (1 - point[1] / point[3]) * 0.5 * this.canvas.height;

        return { x: screenX, y: screenY };
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

        // Get canvas rect for boundary calculation
        const rect = this.canvas.getBoundingClientRect();

        // Calculate 45° diagonal from click point
        const canvasEdgeX = event.clientX > rect.left + rect.width / 2 ?
            rect.right : rect.left;
        const canvasEdgeY = event.clientY > rect.top + rect.height / 2 ?
            rect.bottom : rect.top;

        // 45° diagonal: equal x and y distances
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

        // Position tooltip near the end of diagonal
        const tooltipX = diagonalEndX + direction.x * 20;
        const tooltipY = diagonalEndY + direction.y * 20;

        this.tooltipCard.style.left = tooltipX + 'px';
        this.tooltipCard.style.top = tooltipY + 'px';
        this.tooltipCard.style.opacity = '1';

        // Draw leader line with 45° diagonal
        if (isClick) {
            this.drawLeaderLine(event.clientX, event.clientY, diagonalEndX, diagonalEndY, tooltipX, tooltipY);
        } else {
            // Simple line for hover
            this.leaderLine.innerHTML = '';
        }
    }

    hideTooltip() {
        this.tooltipCard.style.opacity = '0';
        this.leaderLine.innerHTML = '';
        this.hoveredCell = null;
        this.selectedCell = null;
        this.needsGeometryRebuild = true;
    }

    drawLeaderLine(startX, startY, diagonalEndX, diagonalEndY, tooltipX, tooltipY) {
        // WSJ style: black solid lines
        this.leaderLine.innerHTML = `
            <!-- 45° diagonal from cube -->
            <line
                x1="${startX}"
                y1="${startY}"
                x2="${diagonalEndX}"
                y2="${diagonalEndY}"
                stroke="#000"
                stroke-width="2"
            />
            <!-- Connection to tooltip card -->
            <line
                x1="${diagonalEndX}"
                y1="${diagonalEndY}"
                x2="${tooltipX}"
                y2="${tooltipY}"
                stroke="#000"
                stroke-width="1"
            />
            <!-- Origin dot on cube -->
            <circle cx="${startX}" cy="${startY}" r="5" fill="#000" />
            <!-- End dot at card -->
            <circle cx="${tooltipX}" cy="${tooltipY}" r="3" fill="#000" />
        `;
    }

    render() {
        if (!this.device) return;

        // Only rebuild geometry when hover/selection changes
        if (this.needsGeometryRebuild) {
            console.log('Rebuilding geometry due to interaction');
            this.createGeometry();
            this.needsGeometryRebuild = false;
        }

        this.updateUniforms();

        const commandEncoder = this.device.createCommandEncoder();
        const textureView = this.context.getCurrentTexture().createView();

        const renderPassDescriptor = {
            colorAttachments: [{
                view: textureView,
                clearValue: { r: 1.0, g: 1.0, b: 1.0, a: 0.0 },  // Transparent background
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
        ctx.font = 'bold 16px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('3D Tensor Visualization', this.canvas.width / 2, 30);

        ctx.font = '14px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillText(`${codesProcessed} / ${totalCodes} codes processed`, this.canvas.width / 2, 60);
        ctx.fillText('(WebGPU not available - showing 2D fallback)', this.canvas.width / 2, 85);

        // Draw simple 2D representation
        const cellSize = 40;
        const startX = (this.canvas.width - 10 * cellSize) / 2;
        const startY = 120;

        for (let row = 0; row < 10; row++) {
            for (let col = 0; col < 10; col++) {
                const x = startX + col * cellSize;
                const y = startY + row * cellSize;

                ctx.fillStyle = `rgb(${80 + col * 15}, ${100 + row * 10}, 180)`;
                ctx.fillRect(x, y, cellSize - 2, cellSize - 2);
            }
        }

        ctx.fillStyle = '#666';
        ctx.fillText(`10×10 matrix per code layer`, this.canvas.width / 2, startY + 11 * cellSize);
    }
}

// Initialize visualization
function initTensorVisualization(canvasId, data) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new TensorVisualization(canvasId, data);
        });
    } else {
        new TensorVisualization(canvasId, data);
    }
}
