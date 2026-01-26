        // Custom SVG chart implementation
        function createSVGChart(containerId, data, primaryColor, chartTitle, globalMaxThroughput, globalMaxBatchSize) {
            const container = document.getElementById(containerId);
            // Use smaller width for print to prevent overflow
            let width = container.clientWidth || 600;
            // Constrain width to max 550px to fit within print margins
            width = Math.min(width, 550);
            const height = 350;
            const margin = { top: 60, right: 70, bottom: 60, left: 70 };
            const chartWidth = width - margin.left - margin.right;
            const chartHeight = height - margin.top - margin.bottom;

            // Create SVG
            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', width);
            svg.setAttribute('height', height);
            svg.style.fontFamily = 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
            svg.style.fontSize = '12px';

            // Add chart title
            const titleText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            titleText.setAttribute('x', width / 2);
            titleText.setAttribute('y', 25);
            titleText.setAttribute('text-anchor', 'middle');
            titleText.style.fontSize = '16px';
            titleText.style.fontWeight = 'bold';
            titleText.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
            titleText.textContent = chartTitle;
            svg.appendChild(titleText);

            // Process and SORT data by timestamp to fix ordering issues
            const dataPoints = [];
            if (data.times) {
                for (let i = 0; i < data.times.length; i++) {
                    dataPoints.push({
                        time: new Date(data.times[i]).getTime(),
                        throughput: data.throughput ? data.throughput[i] : null,
                        batchSize: data.batch_size ? data.batch_size[i] : null
                    });
                }
                // Sort by timestamp to ensure proper chronological order
                dataPoints.sort((a, b) => a.time - b.time);
            }

            const times = dataPoints.map(d => d.time);
            const throughput = dataPoints.map(d => d.throughput);
            const batchSize = dataPoints.map(d => d.batchSize);

            if (times.length === 0) {
                container.innerHTML = '<div style="text-align: center; padding: 50px; color: #999;">No data available</div>';
                return;
            }

            // Detect time segments (gaps > 5 minutes create new segments)
            const segments = [];
            let currentSegment = { start: times[0], end: times[0], startIdx: 0, endIdx: 0 };

            for (let i = 1; i < times.length; i++) {
                if (times[i] - times[i-1] > 300000) { // 5 minute gap
                    currentSegment.end = times[i-1];
                    currentSegment.endIdx = i-1;
                    segments.push(currentSegment);
                    currentSegment = { start: times[i], end: times[i], startIdx: i, endIdx: i };
                } else {
                    currentSegment.end = times[i];
                    currentSegment.endIdx = i;
                }
            }
            segments.push(currentSegment);

            // Calculate segment widths proportionally with gaps
            const totalDataTime = segments.reduce((sum, seg) => sum + (seg.end - seg.start), 0);
            const gapWidth = 8; // Reduced pixels for each gap to accommodate many gaps
            const availableWidth = chartWidth - (gapWidth * (segments.length - 1));

            // Create scale function that accounts for gaps
            const xScale = (time, idx) => {
                let x = 0;
                let segmentFound = false;

                for (let i = 0; i < segments.length; i++) {
                    const seg = segments[i];
                    if (idx >= seg.startIdx && idx <= seg.endIdx) {
                        const segmentWidth = ((seg.end - seg.start) / totalDataTime) * availableWidth;
                        const positionInSegment = (time - seg.start) / (seg.end - seg.start || 1);
                        x += positionInSegment * segmentWidth;
                        segmentFound = true;
                        break;
                    }
                    // Add width of previous segments plus gaps
                    const segmentWidth = ((seg.end - seg.start) / totalDataTime) * availableWidth;
                    x += segmentWidth + gapWidth;
                }

                return segmentFound ? x : 0;
            };

            const minTime = Math.min(...times);
            const maxTime = Math.max(...times);
            const maxThroughput = globalMaxThroughput || 1;
            const maxBatchSize = globalMaxBatchSize || 10;

            const yScaleThroughput = (value) => chartHeight - (value / maxThroughput) * chartHeight;
            const yScaleBatch = (value) => chartHeight - (value / maxBatchSize) * chartHeight;

            // Create main group
            const mainGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            mainGroup.setAttribute('transform', `translate(${margin.left},${margin.top})`);

            // Draw grid lines
            const gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            gridGroup.style.stroke = '#e0e0e0';
            gridGroup.style.strokeWidth = '0.5';

            // Horizontal grid lines
            for (let i = 0; i <= 5; i++) {
                const y = (chartHeight / 5) * i;
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', 0);
                line.setAttribute('y1', y);
                line.setAttribute('x2', chartWidth);
                line.setAttribute('y2', y);
                gridGroup.appendChild(line);
            }

            mainGroup.appendChild(gridGroup);

            // Draw axes
            const axesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            axesGroup.style.stroke = '#333';
            axesGroup.style.strokeWidth = '1';
            axesGroup.style.fill = 'none';

            // X-axis
            const xAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            xAxis.setAttribute('x1', 0);
            xAxis.setAttribute('y1', chartHeight);
            xAxis.setAttribute('x2', chartWidth);
            xAxis.setAttribute('y2', chartHeight);
            axesGroup.appendChild(xAxis);

            // Y-axes
            const yAxisLeft = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            yAxisLeft.setAttribute('x1', 0);
            yAxisLeft.setAttribute('y1', 0);
            yAxisLeft.setAttribute('x2', 0);
            yAxisLeft.setAttribute('y2', chartHeight);
            axesGroup.appendChild(yAxisLeft);

            const yAxisRight = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            yAxisRight.setAttribute('x1', chartWidth);
            yAxisRight.setAttribute('y1', 0);
            yAxisRight.setAttribute('x2', chartWidth);
            yAxisRight.setAttribute('y2', chartHeight);
            axesGroup.appendChild(yAxisRight);

            mainGroup.appendChild(axesGroup);

            // Draw throughput line with explicit gap handling
            const throughputPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            let pathData = '';
            let inSegment = false;

            for (let i = 0; i < times.length; i++) {
                if (throughput[i] !== null && throughput[i] !== undefined) {
                    const x = xScale(times[i], i);
                    const y = yScaleThroughput(throughput[i]);

                    // Check for time gap (> 5 minutes)
                    if (i > 0 && times[i] - times[i-1] > 300000) {
                        inSegment = false;  // Start new segment after gap
                    }

                    if (!inSegment) {
                        pathData += ` M ${x} ${y}`;
                        inSegment = true;
                    } else {
                        pathData += ` L ${x} ${y}`;
                    }
                } else {
                    inSegment = false;  // Break segment on null
                }
            }

            throughputPath.setAttribute('d', pathData);
            throughputPath.style.stroke = primaryColor;
            throughputPath.style.strokeWidth = '2';
            throughputPath.style.strokeDasharray = '5,5';
            throughputPath.style.fill = 'none';
            mainGroup.appendChild(throughputPath);

            // Draw batch size line (stepped)
            const batchPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            pathData = '';
            inSegment = false;

            for (let i = 0; i < times.length; i++) {
                if (batchSize[i] !== null && batchSize[i] !== undefined) {
                    const x = xScale(times[i], i);
                    const y = yScaleBatch(batchSize[i]);

                    // Check for time gap
                    if (i > 0 && times[i] - times[i-1] > 300000) {
                        inSegment = false;
                    }

                    if (!inSegment) {
                        pathData += ` M ${x} ${y}`;
                        inSegment = true;
                    } else {
                        // Stepped line
                        const prevX = xScale(times[i-1], i-1);
                        pathData += ` L ${x} ${yScaleBatch(batchSize[i-1])} L ${x} ${y}`;
                    }
                } else {
                    inSegment = false;
                }
            }

            batchPath.setAttribute('d', pathData);
            batchPath.style.stroke = '#666';
            batchPath.style.strokeWidth = '1.5';
            batchPath.style.strokeDasharray = '5,5';
            batchPath.style.fill = 'none';
            mainGroup.appendChild(batchPath);

            // Add axis labels
            const labelsGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            labelsGroup.style.fill = '#333';

            // Y-axis labels (left - throughput)
            for (let i = 0; i <= 5; i++) {
                const value = (maxThroughput / 5) * (5 - i);
                const y = (chartHeight / 5) * i;
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', -10);
                text.setAttribute('y', y + 4);
                text.setAttribute('text-anchor', 'end');
                text.style.fill = primaryColor;
                text.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
                // Format small numbers properly (show 3 decimal places for readability)
                text.textContent = value.toFixed(3);
                labelsGroup.appendChild(text);
            }

            // Y-axis labels (right - batch size)
            // Use unique values only to avoid duplicates
            const uniqueBatchSizes = [...new Set(batchSize.filter(v => v !== null))].sort((a, b) => b - a);
            if (uniqueBatchSizes.length > 0) {
                uniqueBatchSizes.forEach((value, idx) => {
                    const y = yScaleBatch(value);
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', chartWidth + 10);
                    text.setAttribute('y', y + 4);
                    text.setAttribute('text-anchor', 'start');
                    text.style.fill = '#666';
                    text.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
                    text.textContent = value;
                    labelsGroup.appendChild(text);
                });
            }

            // X-axis labels (time) - show labels with smart spacing to prevent overlap
            const minLabelSpacing = 80; // Minimum pixels between labels
            let lastLabelX = -minLabelSpacing;

            segments.forEach((segment, segIdx) => {
                const startDate = new Date(segment.start);
                const startX = xScale(segment.start, segment.startIdx);

                // Only show label if it won't overlap with previous one
                if (startX - lastLabelX >= minLabelSpacing) {
                    const startText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    startText.setAttribute('x', startX);
                    startText.setAttribute('y', chartHeight + 20);
                    startText.setAttribute('text-anchor', segIdx === 0 ? 'start' : 'middle');
                    startText.style.fontSize = '10px';
                    startText.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';

                    // First label shows full date, others show time only
                    if (segIdx === 0) {
                        startText.textContent = startDate.toLocaleString([], {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                    } else {
                        startText.textContent = startDate.toLocaleString([], {
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                    }

                    labelsGroup.appendChild(startText);
                    lastLabelX = startX;
                }

                // Add end label for last segment if space permits
                if (segIdx === segments.length - 1 && segment.endIdx > segment.startIdx) {
                    const endX = xScale(segment.end, segment.endIdx);
                    if (endX - lastLabelX >= minLabelSpacing) {
                        const endDate = new Date(segment.end);
                        const endText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        endText.setAttribute('x', endX);
                        endText.setAttribute('y', chartHeight + 20);
                        endText.setAttribute('text-anchor', 'end');
                        endText.style.fontSize = '10px';
                        endText.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
                        endText.textContent = endDate.toLocaleString([], {
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                        labelsGroup.appendChild(endText);
                    }
                }
            })

            // Axis titles
            const throughputTitle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            throughputTitle.setAttribute('x', -chartHeight / 2);
            throughputTitle.setAttribute('y', -50);
            throughputTitle.setAttribute('transform', 'rotate(-90 0 0)');
            throughputTitle.setAttribute('text-anchor', 'middle');
            throughputTitle.style.fill = primaryColor;
            throughputTitle.style.fontWeight = 'bold';
            throughputTitle.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
            throughputTitle.textContent = 'Throughput (items/min)';
            labelsGroup.appendChild(throughputTitle);

            const batchTitle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            batchTitle.setAttribute('x', chartHeight / 2);
            batchTitle.setAttribute('y', -width + 50);
            batchTitle.setAttribute('transform', `rotate(90 0 0)`);
            batchTitle.setAttribute('text-anchor', 'middle');
            batchTitle.style.fill = '#666';
            batchTitle.style.fontWeight = 'bold';
            batchTitle.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
            batchTitle.textContent = 'Batch Size';
            labelsGroup.appendChild(batchTitle);

            const timeTitle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            timeTitle.setAttribute('x', chartWidth / 2);
            timeTitle.setAttribute('y', chartHeight + 45);
            timeTitle.setAttribute('text-anchor', 'middle');
            timeTitle.style.fontWeight = 'bold';
            timeTitle.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
            timeTitle.textContent = 'Time';
            labelsGroup.appendChild(timeTitle);

            mainGroup.appendChild(labelsGroup);

            // Add legend
            const legendGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            legendGroup.setAttribute('transform', `translate(${chartWidth / 2 - 100}, -20)`);

            // Throughput legend
            const throughputLegendLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            throughputLegendLine.setAttribute('x1', 0);
            throughputLegendLine.setAttribute('y1', 0);
            throughputLegendLine.setAttribute('x2', 20);
            throughputLegendLine.setAttribute('y2', 0);
            throughputLegendLine.style.stroke = primaryColor;
            throughputLegendLine.style.strokeWidth = '2';
            throughputLegendLine.style.strokeDasharray = '5,5';
            legendGroup.appendChild(throughputLegendLine);

            const throughputLegendText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            throughputLegendText.setAttribute('x', 25);
            throughputLegendText.setAttribute('y', 4);
            throughputLegendText.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
            throughputLegendText.textContent = 'Throughput';
            legendGroup.appendChild(throughputLegendText);

            // Batch size legend
            const batchLegendLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            batchLegendLine.setAttribute('x1', 100);
            batchLegendLine.setAttribute('y1', 0);
            batchLegendLine.setAttribute('x2', 120);
            batchLegendLine.setAttribute('y2', 0);
            batchLegendLine.style.stroke = '#666';
            batchLegendLine.style.strokeWidth = '1.5';
            batchLegendLine.style.strokeDasharray = '5,5';
            legendGroup.appendChild(batchLegendLine);

            const batchLegendText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            batchLegendText.setAttribute('x', 125);
            batchLegendText.setAttribute('y', 4);
            batchLegendText.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
            batchLegendText.textContent = 'Batch Size';
            legendGroup.appendChild(batchLegendText);

            mainGroup.appendChild(legendGroup);

            // Add invisible circles for hover interaction
            const hoverGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');

            for (let i = 0; i < times.length; i++) {
                if (throughput[i] !== null && throughput[i] !== undefined) {
                    const x = xScale(times[i], i);
                    const y = yScaleThroughput(throughput[i]);

                    // Create larger invisible circle for easier hovering
                    const hoverCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    hoverCircle.setAttribute('cx', x);
                    hoverCircle.setAttribute('cy', y);
                    hoverCircle.setAttribute('r', 8);
                    hoverCircle.style.fill = 'transparent';
                    hoverCircle.style.cursor = 'pointer';

                    // Create visible dot (removed for cleaner charts with many points)
                    // const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    // dot.setAttribute('cx', x);
                    // dot.setAttribute('cy', y);
                    // dot.setAttribute('r', 3);
                    // dot.style.fill = primaryColor;
                    // dot.style.stroke = '#fff';
                    // dot.style.strokeWidth = '2';

                    // Store data for tooltip
                    const dataPoint = {
                        time: times[i],
                        throughput: throughput[i],
                        batchSize: batchSize[i]
                    };

                    // Add hover events
                    hoverCircle.addEventListener('mouseenter', function(e) {
                        // (Dot enlargement removed since dots are not visible)

                        // Create tooltip
                        const tooltip = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                        tooltip.id = 'tooltip-' + i;

                        const date = new Date(dataPoint.time);
                        const timeStr = date.toLocaleString([], {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                        });

                        const text1 = `Time: ${timeStr}`;
                        const text2 = `Throughput: ${dataPoint.throughput.toFixed(3)} items/min`;
                        const text3 = `Batch Size: ${dataPoint.batchSize || 'N/A'}`;

                        // Calculate tooltip position
                        let tooltipX = x + 10;
                        let tooltipY = y - 40;

                        // Adjust if too close to edges
                        if (tooltipX + 180 > chartWidth) tooltipX = x - 190;
                        if (tooltipY < 0) tooltipY = y + 10;

                        // Background rectangle
                        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                        rect.setAttribute('x', tooltipX);
                        rect.setAttribute('y', tooltipY);
                        rect.setAttribute('width', 180);
                        rect.setAttribute('height', 55);
                        rect.setAttribute('rx', 4);
                        rect.style.fill = '#333';
                        rect.style.opacity = '0.95';
                        tooltip.appendChild(rect);

                        // Text lines
                        [text1, text2, text3].forEach((text, idx) => {
                            const textEl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                            textEl.setAttribute('x', tooltipX + 8);
                            textEl.setAttribute('y', tooltipY + 16 + (idx * 16));
                            textEl.style.fill = '#fff';
                            textEl.style.fontSize = '11px';
                            textEl.style.fontFamily = '-apple-system, BlinkMacSystemFont, sans-serif';
                            textEl.textContent = text;
                            tooltip.appendChild(textEl);
                        });

                        mainGroup.appendChild(tooltip);
                    });

                    hoverCircle.addEventListener('mouseleave', function(e) {
                        // (Dot size restore removed since dots are not visible)

                        // Remove tooltip
                        const tooltip = document.getElementById('tooltip-' + i);
                        if (tooltip) tooltip.remove();
                    });

                    // hoverGroup.appendChild(dot); // Removed - no visible dots
                    hoverGroup.appendChild(hoverCircle);
                }
            }

            mainGroup.appendChild(hoverGroup);

            svg.appendChild(mainGroup);
            container.innerHTML = '';
            container.appendChild(svg);
        }

        // Calculate global min/max for consistent Y-axis across charts
        const allThroughputData = [...claudeData.throughput, ...codexData.throughput].filter(v => v !== null);
        const allBatchSizeData = [...claudeData.batch_size, ...codexData.batch_size].filter(v => v !== null);
        const globalMaxThroughput = Math.max(...allThroughputData);
        const globalMaxBatchSize = Math.max(...allBatchSizeData);

        // Create both charts with same color and shared scales
        createSVGChart('claudeChart', claudeData, '#0066cc', 'ANTHROPIC (CLAUDE)', globalMaxThroughput, globalMaxBatchSize);
        createSVGChart('codexChart', codexData, '#0066cc', 'OPENAI (CODEX)', globalMaxThroughput, globalMaxBatchSize);

        // Manage h1 sticky behavior to fix transparency gaps
        function manageStickyBackground() {
            const h1 = document.querySelector('h1');
            if (!h1) return;

            // Check if h1 is stuck (at top of viewport) or in natural position
            const h1Rect = h1.getBoundingClientRect();
            const isH1Stuck = Math.abs(h1Rect.top - 0) < 1;

            // H1 should be visible when it's in its natural position (not stuck)
            const h1ShouldBeVisible = !isH1Stuck;

            // Get all sticky elements
            const chapterTitles = Array.from(document.querySelectorAll('.chapter-title'));
            const modelNames = Array.from(document.querySelectorAll('.model-name'));
            const sectionHeaders = Array.from(document.querySelectorAll('.model-section h3'));

            const allStickies = [...chapterTitles, ...modelNames, ...sectionHeaders];

            // Check which stickies are currently stuck at the top
            const stuckStickies = allStickies.filter(el => {
                const rect = el.getBoundingClientRect();
                const computedStyle = getComputedStyle(el);
                const topValue = parseInt(computedStyle.top) || 0;
                // Element is stuck if it's at its sticky position
                return Math.abs(rect.top - topValue) < 1;
            });

            // Calculate the bottom position of the lowest sticky header
            let maxBottom = 0;
            stuckStickies.forEach(sticky => {
                const rect = sticky.getBoundingClientRect();
                if (rect.bottom > maxBottom) {
                    maxBottom = rect.bottom;
                }
            });

            // Position prediction text elements below the sticky area
            const predictionTexts = document.querySelectorAll('.prediction-text');
            predictionTexts.forEach(text => {
                text.style.top = maxBottom + 'px';
            });

            // Calculate new bottom including stuck prediction texts
            let maxBottomWithPredictions = maxBottom;
            predictionTexts.forEach(text => {
                const textRect = text.getBoundingClientRect();
                const computedTop = parseInt(getComputedStyle(text).top) || 0;
                // Check if prediction text is stuck
                if (Math.abs(textRect.top - computedTop) < 1 && textRect.top >= 0) {
                    if (textRect.bottom > maxBottomWithPredictions) {
                        maxBottomWithPredictions = textRect.bottom;
                    }
                }
            });

            // Position all table headers below prediction texts
            const allTheads = document.querySelectorAll('thead');
            allTheads.forEach(thead => {
                thead.style.top = maxBottomWithPredictions + 'px';
            });

            // If any sticky is active OR we're not at the top, hide h1 text
            if (stuckStickies.length > 0 || !h1ShouldBeVisible) {
                h1.style.color = 'transparent';
                h1.style.borderColor = 'transparent';

                // Expand h1 height to cover up to the lowest sticky
                const h1Top = h1Rect.top;
                const neededHeight = maxBottom - h1Top;
                h1.style.minHeight = neededHeight + 'px';

                // Add border when expanded
                h1.style.borderBottom = '1px solid #000';
            } else {
                // Restore h1 visibility when at top and no stickies are covering it
                h1.style.color = '';
                h1.style.borderColor = '';
                h1.style.minHeight = '';
            }
        }

        // Run on scroll and initially
        window.addEventListener('scroll', manageStickyBackground);
        window.addEventListener('resize', manageStickyBackground);
        manageStickyBackground();

