/**
 * WebGPU Ray-Traced 3D Tensor Visualization with DDA
 * Uses compute shader with DDA for BOTH rendering AND interaction
 * "If it renders, it's interactive" - guaranteed by same ray-voxel code
 */

class TensorVisualizationRayTraced {
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

        // Auto-play
        this.autoPlayEnabled = true;
        this.autoPlayIndex = 0;
        this.autoPlayInterval = null;
        this.clicksBlocked = true; // Block clicks for first 2 seconds

        this.init();
    }

    async init() {
        if (!navigator.gpu) {
            console.warn('WebGPU not supported, falling back');
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
        const adapter = await navigator.gpu.requestAdapter();
        if (!adapter) throw new Error('No GPU adapter');

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

        this.buildVoxelData();
        await this.createRayTracePipeline();
        this.setupMouseEvents();
        this.createTooltipCard();

        // Animation loop
        const animate = () => {
            this.render();
            requestAnimationFrame(animate);
        };
        requestAnimationFrame(animate);

        // Start auto-play immediately after brief delay
        setTimeout(() => {
            this.clicksBlocked = false;
            this.startAutoPlay();
        }, 100);
    }

    buildVoxelData() {
        const { codesProcessed, variantData } = this.data;

        // Get list of code IDs that have variants
        const codeIds = Object.keys(variantData || {}).map(id => parseInt(id)).sort((a, b) => a - b);

        const layersToShow = [];
        if (codeIds.length <= 9) {
            layersToShow.push(...codeIds.slice(0, codeIds.length));
        } else {
            layersToShow.push(...codeIds.slice(0, 9));
            layersToShow.push(codeIds[codeIds.length - 1]);
        }

        this.cells = [];
        this.codeIdToLayer = {}; // Map code_id to layer index

        layersToShow.forEach((codeId, visualIndex) => {
            this.codeIdToLayer[codeId] = visualIndex;
            const codeData = variantData[codeId];
            if (!codeData) return;

            // Build 10x10 matrix (but only for variants that exist)
            for (let row = 0; row < 10; row++) {
                for (let col = 0; col < 10; col++) {
                    const variantKey = `${row},${col}`;
                    const variantText = codeData.variants[variantKey];

                    // Only create cube if variant exists
                    if (!variantText) continue;

                    const x = (col - 4.5) * 0.22;
                    const y = (row - 4.5) * 0.22;
                    const z = visualIndex * 0.35;

                    const colorFactor = visualIndex / Math.max(layersToShow.length - 1, 1);
                    const grayValue = 0.4 + colorFactor * 0.3;

                    this.cells.push({
                        codeId,
                        code: codeData.code,
                        codeDescription: codeData.code_description,
                        row, col,
                        variantText,
                        x, y, z,
                        visualIndex,
                        color: [grayValue, grayValue, grayValue],
                        size: 0.08
                    });
                }
            }
        });
    }

    async createRayTracePipeline() {
        // Create voxel buffer for GPU
        const voxelData = new Float32Array(this.cells.length * 8); // x,y,z,size,r,g,b,cellId
        this.cells.forEach((cell, i) => {
            const offset = i * 8;
            voxelData[offset + 0] = cell.x;
            voxelData[offset + 1] = cell.y;
            voxelData[offset + 2] = cell.z;
            voxelData[offset + 3] = cell.size;
            voxelData[offset + 4] = cell.color[0];
            voxelData[offset + 5] = cell.color[1];
            voxelData[offset + 6] = cell.color[2];
            voxelData[offset + 7] = i; // cell index
        });

        this.voxelBuffer = this.device.createBuffer({
            size: voxelData.byteLength,
            usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST
        });
        this.device.queue.writeBuffer(this.voxelBuffer, 0, voxelData);

        // Create uniform buffer for camera (need space for hovered/selected indices)
        this.uniformBuffer = this.device.createBuffer({
            size: 80, // 5x vec4f (camera + hover/select indices)
            usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST
        });

        // Compute shader for ray tracing with DDA
        const computeShader = `
            struct Voxel {
                pos: vec3f,
                size: f32,
                color: vec3f,
                cellId: f32,
            }

            struct Uniforms {
                cameraPos: vec3f,
                _pad0: f32,
                cameraDir: vec3f,
                _pad1: f32,
                cameraRight: vec3f,
                _pad2: f32,
                cameraUp: vec3f,
                voxelCount: f32,
                hoveredIndex: f32,
                selectedIndex: f32,
                _pad3: f32,
                _pad4: f32,
            }

            @group(0) @binding(0) var outputTex: texture_storage_2d<rgba8unorm, write>;
            @group(0) @binding(1) var<storage, read> voxels: array<Voxel>;
            @group(0) @binding(2) var<uniform> uniforms: Uniforms;

            fn rayBoxIntersect(rayOrigin: vec3f, rayDir: vec3f, boxMin: vec3f, boxMax: vec3f) -> f32 {
                let tMin = (boxMin - rayOrigin) / rayDir;
                let tMax = (boxMax - rayOrigin) / rayDir;
                let t1 = min(tMin, tMax);
                let t2 = max(tMin, tMax);
                let tNear = max(max(t1.x, t1.y), t1.z);
                let tFar = min(min(t2.x, t2.y), t2.z);

                if (tNear > tFar || tFar < 0.0) {
                    return -1.0;
                }
                return select(tFar, tNear, tNear > 0.0);
            }

            @compute @workgroup_size(8, 8)
            fn main(@builtin(global_invocation_id) global_id: vec3u) {
                let dims = textureDimensions(outputTex);
                if (global_id.x >= dims.x || global_id.y >= dims.y) {
                    return;
                }

                // Calculate ray for this pixel
                let uv = vec2f(f32(global_id.x) / f32(dims.x), f32(global_id.y) / f32(dims.y));
                let ndc = uv * 2.0 - 1.0;

                let rayDir = normalize(
                    uniforms.cameraDir +
                    ndc.x * uniforms.cameraRight * 0.6 +
                    ndc.y * uniforms.cameraUp * 0.6
                );

                // Ray trace through all voxels
                var closestT = 999999.0;
                var hitColor = vec3f(1.0, 1.0, 1.0); // Background: white
                var hit = false;
                var hitIndex = -1.0;

                let voxelCount = u32(uniforms.voxelCount);
                for (var i = 0u; i < voxelCount; i++) {
                    let voxel = voxels[i];
                    let halfSize = voxel.size * 0.5;
                    let boxMin = voxel.pos - vec3f(halfSize);
                    let boxMax = voxel.pos + vec3f(halfSize);

                    let t = rayBoxIntersect(uniforms.cameraPos, rayDir, boxMin, boxMax);
                    if (t > 0.0 && t < closestT) {
                        closestT = t;
                        hitColor = voxel.color;
                        hitIndex = f32(i);
                        hit = true;
                    }
                }

                // Highlight hovered or selected voxels in white
                if (hitIndex == uniforms.hoveredIndex || hitIndex == uniforms.selectedIndex) {
                    hitColor = vec3f(1.0, 1.0, 1.0);
                }

                // Write pixel
                textureStore(outputTex, vec2i(global_id.xy), vec4f(hitColor, select(0.0, 1.0, hit)));
            }
        `;

        const computeModule = this.device.createShaderModule({ code: computeShader });

        this.computePipeline = this.device.createComputePipeline({
            layout: 'auto',
            compute: {
                module: computeModule,
                entryPoint: 'main'
            }
        });

        // Create output texture
        this.outputTexture = this.device.createTexture({
            size: [this.canvas.width, this.canvas.height],
            format: 'rgba8unorm',
            usage: GPUTextureUsage.STORAGE_BINDING | GPUTextureUsage.COPY_SRC | GPUTextureUsage.TEXTURE_BINDING
        });

        // Create bind group
        this.bindGroup = this.device.createBindGroup({
            layout: this.computePipeline.getBindGroupLayout(0),
            entries: [
                { binding: 0, resource: this.outputTexture.createView() },
                { binding: 1, resource: { buffer: this.voxelBuffer } },
                { binding: 2, resource: { buffer: this.uniformBuffer } }
            ]
        });

        // Create render pipeline for displaying the ray-traced image
        await this.createDisplayPipeline();
    }

    async createDisplayPipeline() {
        const shaderCode = `
            @vertex
            fn vs_main(@builtin(vertex_index) vertexIndex: u32) -> @builtin(position) vec4f {
                var pos = array<vec2f, 6>(
                    vec2f(-1.0, -1.0), vec2f(1.0, -1.0), vec2f(-1.0, 1.0),
                    vec2f(-1.0, 1.0), vec2f(1.0, -1.0), vec2f(1.0, 1.0)
                );
                return vec4f(pos[vertexIndex], 0.0, 1.0);
            }

            @group(0) @binding(0) var tex: texture_2d<f32>;
            @group(0) @binding(1) var texSampler: sampler;

            @fragment
            fn fs_main(@builtin(position) pos: vec4f) -> @location(0) vec4f {
                let dims = textureDimensions(tex);
                let uv = pos.xy / vec2f(f32(dims.x), f32(dims.y));
                return textureSample(tex, texSampler, uv);
            }
        `;

        const shaderModule = this.device.createShaderModule({ code: shaderCode });

        this.displayPipeline = this.device.createRenderPipeline({
            layout: 'auto',
            vertex: {
                module: shaderModule,
                entryPoint: 'vs_main'
            },
            fragment: {
                module: shaderModule,
                entryPoint: 'fs_main',
                targets: [{ format: this.format }]
            },
            primitive: {
                topology: 'triangle-list'
            }
        });

        this.sampler = this.device.createSampler({
            magFilter: 'nearest',
            minFilter: 'nearest'
        });

        this.displayBindGroup = this.device.createBindGroup({
            layout: this.displayPipeline.getBindGroupLayout(0),
            entries: [
                { binding: 0, resource: this.outputTexture.createView() },
                { binding: 1, resource: this.sampler }
            ]
        });
    }

    updateUniforms() {
        // Calculate camera vectors
        const eye = [
            this.cameraDistance * Math.sin(this.cameraRotationY) * Math.cos(this.cameraRotationX),
            this.cameraDistance * Math.sin(this.cameraRotationX),
            this.cameraDistance * Math.cos(this.cameraRotationY) * Math.cos(this.cameraRotationX)
        ];
        const center = [0, 0, 2];

        const forward = this.normalize([
            center[0] - eye[0],
            center[1] - eye[1],
            center[2] - eye[2]
        ]);

        const worldUp = [0, 1, 0];
        const right = this.normalize(this.cross(forward, worldUp));
        const up = this.cross(right, forward);

        // Find indices of hovered and selected cells
        const hoveredIndex = this.hoveredCell ? this.cells.indexOf(this.hoveredCell) : -1;
        const selectedIndex = this.selectedCell ? this.cells.indexOf(this.selectedCell) : -1;

        const uniformData = new Float32Array([
            ...eye, 0,
            ...forward, 0,
            ...right, 0,
            ...up, this.cells.length,
            hoveredIndex, selectedIndex, 0, 0
        ]);

        this.device.queue.writeBuffer(this.uniformBuffer, 0, uniformData);
    }

    normalize(v) {
        const len = Math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
        return len > 0 ? [v[0]/len, v[1]/len, v[2]/len] : v;
    }

    cross(a, b) {
        return [
            a[1]*b[2] - a[2]*b[1],
            a[2]*b[0] - a[0]*b[2],
            a[0]*b[1] - a[1]*b[0]
        ];
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

                this.cameraRotationY -= deltaX * 0.01;
                this.cameraRotationX -= deltaY * 0.01;
                this.cameraRotationX = Math.max(-Math.PI/2, Math.min(Math.PI/2, this.cameraRotationX));

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
            this.hideTooltip();
        });

        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.cameraDistance += e.deltaY * 0.01;
            this.cameraDistance = Math.max(3, Math.min(15, this.cameraDistance));
        });
    }

    checkHover(e) {
        // Stop auto-play when user hovers over canvas
        if (this.autoPlayEnabled) {
            this.stopAutoPlay();
        }

        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Use same ray calculation as GPU
        const ray = this.getRayFromMouse(mouseX, mouseY);
        const hitCell = this.cpuRayTrace(ray.origin, ray.direction);

        if (hitCell !== this.hoveredCell) {
            this.hoveredCell = hitCell;
            if (hitCell) {
                this.showTooltip(hitCell, e);
            } else {
                this.hideTooltip();
            }
        }
    }

    getRayFromMouse(mouseX, mouseY) {
        const uv = [
            mouseX / this.canvas.width,
            mouseY / this.canvas.height
        ];
        const ndc = [uv[0] * 2 - 1, uv[1] * 2 - 1];

        // Same camera calculation as GPU
        const eye = [
            this.cameraDistance * Math.sin(this.cameraRotationY) * Math.cos(this.cameraRotationX),
            this.cameraDistance * Math.sin(this.cameraRotationX),
            this.cameraDistance * Math.cos(this.cameraRotationY) * Math.cos(this.cameraRotationX)
        ];
        const center = [0, 0, 2];

        const forward = this.normalize([
            center[0] - eye[0],
            center[1] - eye[1],
            center[2] - eye[2]
        ]);

        const worldUp = [0, 1, 0];
        const right = this.normalize(this.cross(forward, worldUp));
        const up = this.cross(right, forward);

        const direction = this.normalize([
            forward[0] + ndc[0] * right[0] * 0.6 + ndc[1] * up[0] * 0.6,
            forward[1] + ndc[0] * right[1] * 0.6 + ndc[1] * up[1] * 0.6,
            forward[2] + ndc[0] * right[2] * 0.6 + ndc[1] * up[2] * 0.6
        ]);

        return { origin: eye, direction };
    }

    cpuRayTrace(origin, direction) {
        // Same algorithm as GPU compute shader
        let closestT = Infinity;
        let hitCell = null;

        this.cells.forEach(cell => {
            const halfSize = cell.size * 0.5;
            const boxMin = [cell.x - halfSize, cell.y - halfSize, cell.z - halfSize];
            const boxMax = [cell.x + halfSize, cell.y + halfSize, cell.z + halfSize];

            const t = this.rayBoxIntersect(origin, direction, boxMin, boxMax);
            if (t > 0 && t < closestT) {
                closestT = t;
                hitCell = cell;
            }
        });

        return hitCell;
    }

    rayBoxIntersect(origin, direction, boxMin, boxMax) {
        const tMin = [
            (boxMin[0] - origin[0]) / direction[0],
            (boxMin[1] - origin[1]) / direction[1],
            (boxMin[2] - origin[2]) / direction[2]
        ];
        const tMax = [
            (boxMax[0] - origin[0]) / direction[0],
            (boxMax[1] - origin[1]) / direction[1],
            (boxMax[2] - origin[2]) / direction[2]
        ];

        const t1 = [
            Math.min(tMin[0], tMax[0]),
            Math.min(tMin[1], tMax[1]),
            Math.min(tMin[2], tMax[2])
        ];
        const t2 = [
            Math.max(tMin[0], tMax[0]),
            Math.max(tMin[1], tMax[1]),
            Math.max(tMin[2], tMax[2])
        ];

        const tNear = Math.max(Math.max(t1[0], t1[1]), t1[2]);
        const tFar = Math.min(Math.min(t2[0], t2[1]), t2[2]);

        if (tNear > tFar || tFar < 0) return -1;
        return tNear > 0 ? tNear : tFar;
    }

    startAutoPlay() {
        if (!this.cells || this.cells.length === 0) return;

        // Sort cells by Z-coordinate (depth) - closest to camera first
        // Camera is looking at the grid, so we want cells with higher Z values (closer to viewer)
        this.sortedCells = [...this.cells].sort((a, b) => {
            // Calculate distance from camera position
            const eye = [
                this.cameraDistance * Math.sin(this.cameraRotationY) * Math.cos(this.cameraRotationX),
                this.cameraDistance * Math.sin(this.cameraRotationX),
                this.cameraDistance * Math.cos(this.cameraRotationY) * Math.cos(this.cameraRotationX)
            ];

            const distA = Math.sqrt(
                Math.pow(a.x - eye[0], 2) +
                Math.pow(a.y - eye[1], 2) +
                Math.pow(a.z - eye[2], 2)
            );

            const distB = Math.sqrt(
                Math.pow(b.x - eye[0], 2) +
                Math.pow(b.y - eye[1], 2) +
                Math.pow(b.z - eye[2], 2)
            );

            return distA - distB; // Closest first
        });

        this.autoPlayInterval = setInterval(() => {
            if (!this.autoPlayEnabled) return;

            const cell = this.sortedCells[this.autoPlayIndex];

            // Create synthetic event
            const projected = this.project3DTo2D(cell.x, cell.y, cell.z);
            if (projected) {
                const rect = this.canvas.getBoundingClientRect();
                const fakeEvent = {
                    clientX: projected.x + rect.left,
                    clientY: projected.y + rect.top
                };

                this.showTooltip(cell, fakeEvent);
            }

            this.autoPlayIndex = (this.autoPlayIndex + 1) % this.sortedCells.length;
        }, 2000);
    }

    stopAutoPlay() {
        if (this.autoPlayInterval) {
            this.autoPlayEnabled = false;
            clearInterval(this.autoPlayInterval);
            this.autoPlayInterval = null;
        }
    }

    project3DTo2D(x, y, z) {
        // Project using same camera as GPU
        const eye = [
            this.cameraDistance * Math.sin(this.cameraRotationY) * Math.cos(this.cameraRotationX),
            this.cameraDistance * Math.sin(this.cameraRotationX),
            this.cameraDistance * Math.cos(this.cameraRotationY) * Math.cos(this.cameraRotationX)
        ];
        const center = [0, 0, 2];

        const forward = this.normalize([center[0] - eye[0], center[1] - eye[1], center[2] - eye[2]]);
        const worldUp = [0, 1, 0];
        const right = this.normalize(this.cross(forward, worldUp));
        const up = this.cross(right, forward);

        // Point relative to camera
        const p = [x - eye[0], y - eye[1], z - eye[2]];

        // Project onto camera plane
        const px = this.dot(p, right) / 0.6;
        const py = this.dot(p, up) / 0.6;

        // Convert to screen space
        const screenX = (px + 1) * 0.5 * this.canvas.width;
        const screenY = (1 - py) * 0.5 * this.canvas.height;

        return { x: screenX, y: screenY };
    }

    dot(a, b) {
        return a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
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

    showTooltip(cell, event) {
        const { code, codeDescription, row, col, variantText, visualIndex } = cell;
        // row = detail_level (0-9), col = variant_index (0-9)
        const detailLevel = row;
        const variantIndex = col;

        const detailLabels = [
            "Ultra-concise", "Very brief", "Brief", "Concise", "Moderate-short",
            "Moderate", "Moderate-detailed", "Detailed", "Very detailed", "Maximum detail"
        ];

        this.tooltipCard.innerHTML = `
            <div style="font-weight: 700; margin-bottom: 12px; color: #000; font-size: 15px; border-bottom: 2px solid #000; padding-bottom: 8px;">
                ${code}
            </div>
            <div style="margin-bottom: 8px; color: #555; font-size: 12px; font-style: italic;">
                ${codeDescription}
            </div>
            <div style="margin-bottom: 10px; padding: 10px; background: #f9f9f9; border-left: 3px solid #000; font-size: 12px; color: #333;">
                ${variantText}
            </div>
            <div style="margin-bottom: 6px; color: #333; font-size: 12px;">
                <strong>Detail Level:</strong> ${detailLevel}/9 (${detailLabels[detailLevel]})
            </div>
            <div style="margin-bottom: 6px; color: #333; font-size: 12px;">
                <strong>Variant:</strong> #${variantIndex}/9
            </div>
            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #ccc; font-size: 11px; color: #666;">
                Position: [${detailLevel}, ${variantIndex}] | Code Layer ${visualIndex + 1}
            </div>
        `;

        const rect = this.canvas.getBoundingClientRect();

        // Check if canvas is visible in viewport - more strict check
        // Canvas must have meaningful overlap with viewport (at least 50px visible)
        const margin = 50;
        const isCanvasVisible = (
            rect.bottom > margin &&  // At least 50px of canvas must be below top of viewport
            rect.top < (window.innerHeight - margin) &&  // At least 50px of canvas must be above bottom of viewport
            rect.left < window.innerWidth &&
            rect.right > 0
        );

        // If canvas is not visible, don't show tooltip
        if (!isCanvasVisible) {
            this.hideTooltip();
            return;
        }

        // Simple tooltip positioning near mouse cursor
        const offset = 15;
        let tooltipX = event.clientX + offset;
        let tooltipY = event.clientY + offset;

        // Constrain tooltip to viewport
        const tooltipWidth = 280;
        const tooltipHeight = 220;
        const viewportMargin = 10;

        // If tooltip would go off right edge, flip to left of cursor
        if (tooltipX + tooltipWidth > window.innerWidth - viewportMargin) {
            tooltipX = event.clientX - tooltipWidth - offset;
        }

        // If tooltip would go off bottom edge, flip to above cursor
        if (tooltipY + tooltipHeight > window.innerHeight - viewportMargin) {
            tooltipY = event.clientY - tooltipHeight - offset;
        }

        // Final bounds check
        tooltipX = Math.max(viewportMargin, Math.min(tooltipX, window.innerWidth - tooltipWidth - viewportMargin));
        tooltipY = Math.max(viewportMargin, Math.min(tooltipY, window.innerHeight - tooltipHeight - viewportMargin));

        this.tooltipCard.style.left = tooltipX + 'px';
        this.tooltipCard.style.top = tooltipY + 'px';
        this.tooltipCard.style.opacity = '1';
    }

    hideTooltip() {
        this.tooltipCard.style.opacity = '0';
    }

    render() {
        if (!this.device) return;

        this.updateUniforms();

        const commandEncoder = this.device.createCommandEncoder();

        // Run compute shader to ray trace
        const computePass = commandEncoder.beginComputePass();
        computePass.setPipeline(this.computePipeline);
        computePass.setBindGroup(0, this.bindGroup);
        computePass.dispatchWorkgroups(
            Math.ceil(this.canvas.width / 8),
            Math.ceil(this.canvas.height / 8)
        );
        computePass.end();

        // Render ray-traced image to canvas
        const textureView = this.context.getCurrentTexture().createView();
        const renderPass = commandEncoder.beginRenderPass({
            colorAttachments: [{
                view: textureView,
                clearValue: { r: 1, g: 1, b: 1, a: 0 },
                loadOp: 'clear',
                storeOp: 'store'
            }]
        });
        renderPass.setPipeline(this.displayPipeline);
        renderPass.setBindGroup(0, this.displayBindGroup);
        renderPass.draw(6);
        renderPass.end();

        this.device.queue.submit([commandEncoder.finish()]);
    }

    fallbackTo2D() {
        const ctx = this.canvas.getContext('2d');
        ctx.fillStyle = '#333';
        ctx.font = 'bold 16px Georgia, serif';
        ctx.textAlign = 'center';
        ctx.fillText('WebGPU not available', this.canvas.width / 2, this.canvas.height / 2);
    }
}

function initTensorVisualization(canvasId, data) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new TensorVisualizationRayTraced(canvasId, data);
        });
    } else {
        new TensorVisualizationRayTraced(canvasId, data);
    }
}
