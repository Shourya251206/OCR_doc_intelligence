let currentTab = 'purchase-order';
let pdfDoc = null;
let pdfUrl = "";
let currentZoom = 1;
const presetFields = {
    'purchase-order': [
        'Purchase Order Number',
        'Purchase Order Date',
        'Customer Name',
        'Customer Address',
        'Grand Total',
        'Tax',
        'Subtotal',
        'Supplier Name'
    ],
    'contract': [
        'Licensor',
        'Licensee',
        'Registration Number',
        'Effective Date',
        'Termination Date',
        'Governing Law',
        'Jurisdiction'
    ]
};

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    const uploadArea = document.getElementById('upload-area');
    const icon = tab === 'purchase-order' ? '📄' : '📋';
    const title = tab === 'purchase-order' ? 'Purchase Order' : 'Contract';
    
    uploadArea.querySelector('.upload-icon').textContent = icon;
    uploadArea.querySelector('h3').textContent = `Drag & Drop Your ${title}`;
    document.getElementById('uploadForm').action = tab === 'purchase-order' ? '/upload_po' : '/upload_contract';
    
    // Update preset buttons
    // updatePresetButtons(); // This line is removed
}

// Remove updatePresetButtons and all calls to it
// Remove any code referencing 'preset-buttons' or Quick Queries

function scrollToUpload() {
    document.getElementById('upload-area').scrollIntoView({ behavior: 'smooth' });
}

function showLandingPage() {
    document.getElementById('landing-page').style.display = 'block';
    document.getElementById('split-view').style.display = 'none';
    document.querySelector('.back-button').style.display = 'none';
}

function showSplitView() {
    document.getElementById('landing-page').style.display = 'none';
    document.getElementById('split-view').style.display = 'block';
    document.querySelector('.back-button').style.display = 'block';
}

// File upload handling
const fileInput = document.getElementById('file-input');
const uploadArea = document.getElementById('upload-area');

fileInput.addEventListener('change', handleFileSelect);

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#667eea';
    uploadArea.style.background = 'rgba(102, 126, 234, 0.1)';
});

uploadArea.addEventListener('dragleave', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#ddd';
    uploadArea.style.background = 'transparent';
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#ddd';
    uploadArea.style.background = 'transparent';
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelect({ target: { files: files } });
    }
});

async function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    showSplitView();
    document.getElementById('document-name').textContent = file.name;

    const progressBar = document.getElementById('progressBar');
    progressBar.style.display = 'block';
    progressBar.style.width = '0%';

    let progress = 0;
    const fakeProgress = setInterval(() => {
        if (progress < 90) {
            progress += 10;
            progressBar.style.width = progress + '%';
        }
    }, 200);

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(document.getElementById('uploadForm').action, {
            method: 'POST',
            body: formData
        });

        clearInterval(fakeProgress);
        progressBar.style.width = '100%';
        setTimeout(() => {
            progressBar.style.display = 'none';
        }, 500);

        const data = await response.json();
        if (data.pdf_url) {
            pdfUrl = data.pdf_url;
            await renderPDF(pdfUrl);
            renderFieldsOutput(data.mandatory_fields);
            // updatePresetButtons(); // This line is removed
            alert('File uploaded & mandatory fields extracted.');
        } else {
            throw new Error(data.error || 'Upload failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        alert('Error uploading file: ' + error.message);
        showLandingPage();
    }
}

async function renderPDF(url) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';
    pdfDoc = await pdfjsLib.getDocument(url).promise;

    const container = document.getElementById('pdf-container');
    container.innerHTML = '';

    for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.5 * currentZoom });

        const pageWrapper = document.createElement('div');
        pageWrapper.className = 'pdf-page-wrapper';
        pageWrapper.dataset.pageNum = pageNum;
        pageWrapper.style.position = 'relative';
        pageWrapper.style.marginBottom = '20px';

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        pageWrapper.appendChild(canvas);

        const textLayerDiv = document.createElement('div');
        textLayerDiv.className = 'textLayer';
        textLayerDiv.style.height = `${viewport.height}px`;
        textLayerDiv.style.width = `${viewport.width}px`;

        pageWrapper.appendChild(textLayerDiv);
        container.appendChild(pageWrapper);

        await page.render({
            canvasContext: ctx,
            viewport: viewport
        }).promise;

        const textContent = await page.getTextContent();
        pdfjsLib.renderTextLayer({
            textContent,
            container: textLayerDiv,
            viewport: viewport,
            textDivs: []
        });
    }
}

function zoomIn() {
    currentZoom *= 1.2;
    if (pdfUrl) renderPDF(pdfUrl);
}

function zoomOut() {
    currentZoom /= 1.2;
    if (pdfUrl) renderPDF(pdfUrl);
}

function resetZoom() {
    currentZoom = 1;
    if (pdfUrl) renderPDF(pdfUrl);
}

function setQuery(field) {
    const queryInput = document.getElementById('query-input');
    const currentValue = queryInput.value.trim();
    queryInput.value = currentValue ? `${currentValue}, ${field}` : field;
}

async function extractData() {
    const queryInput = document.getElementById('query-input');
    const query = queryInput ? queryInput.value.trim() : '';
    if (!query) {
        alert('Please enter at least one field or select a preset query.');
        return;
    }
    const extractButton = document.getElementById('extract-button');
    const resultsContent = document.getElementById('results-content');
    const progressBar = document.getElementById('progressBar');

    extractButton.disabled = true;
    extractButton.textContent = 'Extracting...';
    if (progressBar) {
        progressBar.style.display = 'block';
        progressBar.style.width = '0%';
    }

    let progress = 0;
    const fakeProgress = setInterval(() => {
        if (progress < 90 && progressBar) {
            progress += 10;
            progressBar.style.width = progress + '%';
        }
    }, 150);

    try {
        // Only request the fields the user entered
        const fields = query.split(',').map(f => f.trim()).filter(f => f);
        const response = await fetch('/get_fields', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ fields })
        });

        clearInterval(fakeProgress);
        if (progressBar) {
            progressBar.style.width = '100%';
            setTimeout(() => {
                progressBar.style.display = 'none';
            }, 500);
        }

        const data = await response.json();
        renderFieldsOutput(data.fields_output, true);
    } catch (error) {
        console.error('Extraction error:', error);
        alert('Error extracting fields: ' + error.message);
    } finally {
        extractButton.disabled = false;
        extractButton.textContent = 'Extract Data';
    }
}

function clearResults() {
    const resultsContent = document.getElementById('results-content');
    if (resultsContent) {
        resultsContent.innerHTML = '<div class="loading-indicator"><p>Results will appear here after extraction...</p></div>';
    }
    const queryInput = document.getElementById('query-input');
    if (queryInput) {
        queryInput.value = '';
    }
}

async function exportResults(format) {
    if (format !== 'csv') {
        alert('Only CSV export is supported.');
        return;
    }

    try {
        const response = await fetch('/save', { method: 'POST' });
        const data = await response.json();
        alert(data.message);
    } catch (error) {
        console.error('Export error:', error);
        alert('Error exporting data: ' + error.message);
    }
}

function renderFieldsOutput(fieldsOutput, append = false) {
    const resultsContent = document.getElementById('results-content');
    if (!append) {
        resultsContent.innerHTML = '';
    }
    const shown = new Set();
    for (const key in fieldsOutput) {
        if (shown.has(key)) continue;
        shown.add(key);
        const fieldObj = fieldsOutput[key];
        const textValue = (fieldObj && typeof fieldObj === 'object' && fieldObj.value) ? fieldObj.value : 'N/A';
        const textToHighlight = (fieldObj && typeof fieldObj === 'object' && Array.isArray(fieldObj.matched_text) && fieldObj.matched_text.length > 0) ? fieldObj.matched_text[0] : '';

        const resultItem = document.createElement('div');
        resultItem.className = 'result-item';

        const resultQuery = document.createElement('div');
        resultQuery.className = 'result-query';
        resultQuery.textContent = key;

        const resultData = document.createElement('div');
        resultData.className = 'result-data';
        resultData.textContent = textValue;

        const resultMeta = document.createElement('div');
        resultMeta.className = 'result-meta';
        resultMeta.innerHTML = `<div class="confidence-score">Confidence: 95%</div>`;

        resultItem.appendChild(resultQuery);
        resultItem.appendChild(resultData);
        resultItem.appendChild(resultMeta);

        if (textToHighlight) {
            // If matched_text is an array, highlight all values
            if (Array.isArray(fieldObj.matched_text)) {
                resultItem.addEventListener('click', () => {
                    fieldObj.matched_text.forEach(txt => highlightAllMatches(txt));
                });
            } else {
                resultItem.addEventListener('click', () => highlightAllMatches(textToHighlight));
            }
        }

        resultsContent.appendChild(resultItem);
    }
}

function highlightAllMatches(searchText) {
    document.querySelectorAll('.textLayer span').forEach(span => {
        if (span.style.backgroundColor) {
            span.style.backgroundColor = 'transparent';
        }
    });

    const textToFind = searchText ? searchText.trim() : '';
    if (!textToFind) return;

    let found = false;
    const textLayers = document.querySelectorAll('.textLayer');
    let firstMatchElement = null;

    textLayers.forEach(layer => {
        const textContent = layer.textContent;
        const spans = Array.from(layer.querySelectorAll('span'));
        const charToSpanMap = [];
        spans.forEach(span => {
            for (const char of span.textContent) {
                charToSpanMap.push(span);
            }
        });

        let startIndex = textContent.indexOf(textToFind);
        while (startIndex !== -1) {
            found = true;
            const endIndex = startIndex + textToFind.length;
            const spansToHighlight = new Set();
            for (let i = startIndex; i < endIndex; i++) {
                spansToHighlight.add(charToSpanMap[i]);
            }

            spansToHighlight.forEach(span => {
                if (span) {
                    span.style.backgroundColor = 'rgba(255, 255, 0, 0.4)';
                    if (!firstMatchElement) {
                        firstMatchElement = span;
                    }
                }
            });

            startIndex = textContent.indexOf(textToFind, startIndex + 1);
        }
    });

    // If not found, try to highlight each word separately
    if (!found && textToFind.split(/\s+/).length > 1) {
        const words = textToFind.split(/\s+/).filter(Boolean);
        words.forEach(word => {
            if (word.length > 2) { // avoid highlighting very short words
                highlightAllMatches(word);
            }
        });
        return;
    }

    if (firstMatchElement) {
        firstMatchElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
        console.warn(`Could not find a match for "${textToFind}".`);
    }
}

// Initialize preset buttons on page load
document.addEventListener('DOMContentLoaded', () => {
    // updatePresetButtons(); // This line is removed
});