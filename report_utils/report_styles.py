"""
WSJ-style CSS for medical coding evaluation reports.
"""

def get_wsj_style() -> str:
    """Return the exact WSJ style from our evaluation report."""


    return """
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    body {
        font-family: Georgia, 'Times New Roman', serif;
        line-height: 1.5;
        color: #000;
        background: #fff;
        padding: 40px 20px;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
    }
    h1 {
        font-size: 36px;
        font-weight: normal;
        margin-bottom: 8px;
        border-bottom: 1px solid #000;
        padding-bottom: 12px;
        position: sticky;
        top: 0;
        background: #fff;
        z-index: 89;
    }
    h2 {
        font-size: 24px;
        font-weight: normal;
        margin: 40px 0 20px 0;
        padding-top: 20px;
        border-top: 1px solid #ddd;
    }
    h3 {
        font-size: 14px;
        font-weight: bold;
        margin: 30px 0 16px 0;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .model-section h3 {
        position: sticky;
        top: 96px;
        background: #fff;
        z-index: 90;
        padding-bottom: 16px;
    }
    .chapter h3 {
        position: sticky;
        top: 60px;
        background: #fff;
        z-index: 95;
        padding-bottom: 10px;
        margin-left: -20px;
        margin-right: -20px;
        padding-left: 20px;
        padding-right: 20px;
    }
    thead {
        position: sticky;
        top: 0;
        z-index: 85;
    }
    .timestamp {
        color: #666;
        font-size: 13px;
        margin-bottom: 40px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .chapter {
        margin: 60px 0;
        padding-top: 40px;
        border-top: 2px solid #000;
    }
    .chapter-title {
        font-size: 28px;
        font-weight: normal;
        margin-bottom: 24px;
        letter-spacing: 0.5px;
        position: sticky;
        top: 0;
        background: #fff;
        z-index: 100;
        padding-bottom: 16px;
    }
    .executive-summary {
        background: #f9f9f9;
        border-left: 3px solid #0066cc;
        padding: 20px;
        margin: 30px 0;
        font-size: 16px;
    }
    .comparison-grid {
        display: grid;
        grid-template-columns: 150px repeat(2, 1fr);
        gap: 1px;
        background: #000;
        border: 1px solid #000;
        margin: 20px 0;
    }
    .comparison-header {
        background: #000;
        color: #fff;
        padding: 12px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 1px;
        text-align: center;
    }
    .comparison-metric {
        background: #f5f5f5;
        padding: 12px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 12px;
        font-weight: bold;
        text-transform: uppercase;
    }
    .comparison-value {
        background: white;
        padding: 12px;
        text-align: center;
        font-size: 20px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .comparison-value.winner {
        background: #e8f4fd;
        font-weight: bold;
    }
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1px;
        background: #ddd;
        border: 1px solid #ddd;
        margin: 30px 0;
    }
    @media (max-width: 1200px) {
        .metrics-grid {
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        }
    }
    .metric-card {
        background: white;
        padding: 20px;
        text-align: center;
    }
    .metric-label {
        font-size: 11px;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .metric-value {
        font-size: 32px;
        font-weight: normal;
        color: #000;
    }
    .metric-detail {
        font-size: 13px;
        color: #666;
        margin-top: 4px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .bar-chart {
        margin: 20px 0;
    }
    .bar-row {
        display: grid;
        grid-template-columns: 120px 1fr 60px;
        align-items: center;
        margin: 8px 0;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 13px;
    }
    .bar-label {
        text-align: right;
        padding-right: 12px;
        font-weight: bold;
    }
    .bar-container {
        background: #f0f0f0;
        height: 24px;
        position: relative;
    }
    .bar {
        height: 100%;
        background: #0066cc;
        position: relative;
    }
    .bar-value {
        padding-left: 8px;
        font-weight: bold;
    }
    .info-box {
        background: #fff;
        border: 1px solid #000;
        padding: 20px;
        margin: 20px 0;
    }
    .info-title {
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 12px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
        position: sticky;
        top: 95px;
        background: #fff;
        z-index: 92;
        padding: 10px 0;
        margin-top: -10px;
        margin-left: -20px;
        margin-right: -20px;
        padding-left: 20px;
        padding-right: 20px;
    }
    .info-box .table-wsj thead {
        position: sticky;
        top: 137px;
        z-index: 91;
    }
    .info-box .table-wsj thead tr {
        background: #000;
    }
    .info-box .table-wsj thead th {
        background: #000;
    }
    .code-block {
        background: #f9f9f9;
        border: 1px solid #ddd;
        padding: 15px;
        margin: 15px 0;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        overflow-x: auto;
    }
    .table-wsj {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        margin: 20px 0;
    }
    .table-wsj th, .table-wsj td {
        padding: 12px 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
    }
    .table-wsj th {
        background: #000;
        color: white;
        font-weight: normal;
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 0.5px;
    }
    .table-wsj tr:hover {
        background: #f8f8f8;
    }
    .chart-placeholder {
        background: #f9f9f9;
        border: 1px solid #ddd;
        padding: 40px;
        text-align: center;
        color: #666;
        font-style: italic;
        margin: 20px 0;
    }
    .toc {
        background: #f9f9f9;
        border: 1px solid #ddd;
        padding: 20px;
        margin: 30px 0;
    }
    .toc-title {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .toc-item {
        margin: 8px 0;
        padding-left: 20px;
        font-size: 14px;
    }
    .highlight-box {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 15px;
        margin: 20px 0;
    }
    .code-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .code-table th, .code-table td {
        padding: 12px 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
    }
    .code-table th {
        background: #000;
        color: white;
        font-weight: normal;
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 0.5px;
    }
    .code-table tr:hover {
        background: #f8f8f8;
    }
    .code-badge {
        display: inline-block;
        padding: 2px 6px;
        font-size: 11px;
        font-family: 'Courier New', monospace;
        background: #f0f0f0;
        border: 1px solid #ddd;
        margin: 2px;
    }
    .comparison-table, .samples-table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
        font-size: 13px;
    }
    .comparison-table th, .samples-table th,
    .comparison-table td, .samples-table td {
        padding: 8px 12px;
        text-align: left;
        border: 1px solid #ddd;
    }
    .comparison-table th, .samples-table th {
        background: #f5f5f5;
        font-weight: bold;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .success { color: #006600; font-weight: bold; }
    .failure { color: #cc0000; font-weight: bold; }
    .tp-badge {
        background: #fff;
        border: 1px solid #000;
        font-weight: bold;
    }
    .fp-badge {
        background: #f0f0f0;
        border: 1px solid #999;
        text-decoration: line-through;
    }
    .fn-badge {
        background: #fff;
        border: 1px dashed #666;
        opacity: 0.7;
    }
    .prediction-card {
        background: white;
        border-top: 1px solid #ddd;
        border-bottom: 1px solid #ddd;
        padding: 20px 0;
        margin-bottom: 20px;
    }
    .prediction-text {
        font-style: italic;
        color: #333;
        margin-bottom: 12px;
        font-size: 14px;
        position: sticky;
        top: 0;
        background: #fff;
        z-index: 86;
        padding: 8px 0;
    }
    .codes-row {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 24px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 13px;
    }
    .codes-label {
        font-size: 11px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #666;
        margin-bottom: 6px;
    }
    .model-section {
        margin: 60px 0;
        padding-top: 40px;
        border-top: 2px solid #000;
    }
    .model-name {
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 24px;
        letter-spacing: 0.5px;
        position: sticky;
        top: 52px;
        background: #fff;
        z-index: 95;
    }
    .insight-box {
        background: #fff;
        border: 1px solid #000;
        padding: 20px;
        margin: 20px 0;
    }
    .insight-title {
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 12px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .performance-chart {
        margin: 40px 0;
    }
    .comparison-section {
        margin: 40px 0;
    }

    /* Print-specific styles for 4-page layout */
    @media print {
        * {
            print-color-adjust: exact;
            -webkit-print-color-adjust: exact;
        }

        @page {
            size: letter;
            margin: 0.75in;
        }

        body {
            font-size: 10pt;
            line-height: 1.3;
            padding: 0;
        }

        .container {
            max-width: 100%;
        }

        /* Disable all sticky positioning for print */
        h1, h2, h3, h4, h5, h6,
        .chapter-title,
        .model-name,
        .prediction-text,
        .info-title,
        thead,
        .info-box thead,
        .info-box .table-wsj thead {
            position: static !important;
            top: auto !important;
        }

        /* Hide elements that shouldn't print */
        canvas {
            max-height: 250px !important;
            page-break-inside: avoid;
        }

        /* Constrain chart containers for print to prevent overflow */
        #claudeChart, #codexChart {
            max-width: 100%;
            overflow: hidden;
        }

        #claudeChart svg, #codexChart svg {
            max-width: 100%;
            height: auto;
        }

        /* Page 1: Title, Executive Summary, TOC, and Chapter 1 */
        h1 {
            font-size: 24pt;
            page-break-after: avoid;
        }

        .executive-summary {
            page-break-after: avoid;
            font-size: 9.5pt;
            line-height: 1.25;
        }

        .toc {
            page-break-after: avoid;
            margin: 20px 0;
        }

        /* Each chapter starts on a new page */
        .chapter {
            page-break-before: always;
            margin: 0;
            padding-top: 0;
        }

        /* First chapter doesn't need page break before */
        .chapter:first-of-type {
            page-break-before: avoid;
        }

        /* Model sections (ANTHROPIC, OPENAI) start on new pages */
        .model-name {
            page-break-before: always;
            margin-top: 0;
            padding-top: 0;
        }

        /* Ensure h3 sections can optionally start new pages for better layout */
        h3 {
            margin-top: 8px;
            margin-bottom: 6px;
            page-break-after: avoid;
        }

        /* Major sections within chapters */
        .chapter h3:nth-of-type(3),
        .chapter h3:nth-of-type(5) {
            page-break-before: auto;
            padding-top: 0;
        }

        /* Keep elements together */
        .chapter-title {
            page-break-after: avoid;
            font-size: 18pt;
        }

        h2, h3 {
            page-break-after: avoid;
            orphans: 3;
            widows: 3;
        }

        .metrics-grid {
            page-break-inside: avoid;
        }

        .comparison-grid {
            page-break-inside: avoid;
        }

        .prediction-card {
            page-break-inside: avoid;
            margin-bottom: 6px;
            padding: 6px 0;
        }

        .insight-box, .highlight-box {
            page-break-inside: avoid;
        }

        /* Each round-trip example on its own page */
        .roundtrip-example {
            page-break-before: always;
            page-break-after: always;
            page-break-inside: auto;
            max-height: 9.5in;
            overflow: hidden;
        }

        /* Base font sizes for print */
        .roundtrip-example .table-wsj {
            font-size: 7.5pt;
        }

        .roundtrip-example .table-wsj td {
            padding: 5px 3px;
            line-height: 1.15;
            word-wrap: break-word;
            max-width: 400px;
        }

        .roundtrip-example .table-wsj th {
            padding: 5px 3px;
            font-size: 7pt;
        }

        /* Compact code badges for print */
        .roundtrip-example .code-badge {
            font-size: 6.5pt;
            padding: 1px 3px;
            margin: 1px 2px 1px 0;
            display: inline-block;
        }

        /* Description column can be narrower if needed */
        .roundtrip-example .table-wsj td:nth-child(2) {
            font-size: 7pt;
            line-height: 1.1;
        }

        /* Restrict code badges column width */
        .roundtrip-example .table-wsj td:nth-child(3) {
            max-width: 90px;
            width: 90px;
        }

        .table-wsj {
            page-break-inside: avoid;
            font-size: 10pt;
            margin: 8px 0;
        }

        .table-wsj th,
        .table-wsj td {
            padding: 5px 4px;
            line-height: 1.25;
        }

        .code-block {
            page-break-inside: avoid;
            font-size: 9.5pt;
        }

        /* Adjust font sizes for print */
        .metric-value {
            font-size: 18pt;
        }

        .comparison-value {
            font-size: 13pt;
        }

        .code-badge {
            font-size: 8pt;
            padding: 1px 4px;
            display: inline-block;
            margin: 1px 2px 1px 0;
        }

        /* For tables with code badges, limit the column width */
        .table-wsj td:has(.code-badge) {
            max-width: 90px;
            width: 90px;
        }

        /* Reduce margins and padding */
        .chapter {
            margin: 0;
            padding-top: 0;
        }

        p {
            margin: 8px 0;
        }

        ul, ol {
            margin: 8px 0;
        }

        .info-box {
            padding: 12px;
            margin: 12px 0;
        }

        .metrics-grid {
            gap: 12px;
        }

        .metric-card {
            padding: 10px;
        }

        /* Compact bar charts for print */
        .bar-chart {
            margin: 8px 0;
            page-break-inside: avoid;
        }

        .bar-row {
            margin: 3px 0;
            font-size: 8pt;
            grid-template-columns: 80px 1fr 50px;
        }

        .bar-container {
            height: 16px;
        }

        .bar-label {
            font-size: 8pt;
        }

        .bar-value {
            font-size: 8pt;
            padding-left: 4px;
        }

        /* Footer adjustments */
        div[style*="margin-top: 60px"] {
            display: none;
        }
    }
    """

