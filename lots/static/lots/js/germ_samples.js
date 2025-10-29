// Germ Samples JavaScript - Exact copy from HTML file

// These variables will be set by the HTML template
// let allBatches, allLots;

let scanningActive = false;
let currentBatch = null;
let samples = [];
let scanInput = '';
let scanTimeout;

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    setupCSRFForFetch(); // Setup CSRF for all fetch requests
    populateBatchDropdown();
    updateUI();
    setupKeyboardListener();
});

// Function to determine sample status
function getSampleStatus(sample, batchStatus) {
    // If batch is still pending, all samples are "scanned"
    if (batchStatus === 'pending') {
        return 'scanned';
    }
    
    // If batch is sent, check germination_rate
    if (batchStatus === 'sent') {
        // If germination_rate exists and > 0, it's completed
        if (sample.germination_rate && sample.germination_rate > 0) {
            return 'completed';
        } else {
            // Otherwise, it's been sent but not tested yet
            return 'germ sent';
        }
    }
    
    return 'scanned'; // fallback
}

// Toast notification system
function showToast(type, title, message, duration = 5000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    toast.innerHTML = `
        <div class="toast-icon">${icons[type] || icons.info}</div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="closeToast(this)">&times;</button>
    `;
    
    container.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add('show'), 100);
    
    // Auto remove
    setTimeout(() => closeToast(toast.querySelector('.toast-close')), duration);
}

function closeToast(button) {
    const toast = button.closest('.toast');
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
}

// Confirmation dialog system
let confirmCallback = null;

function showConfirm(title, message, icon, onConfirm, inputConfig = null) {
    document.getElementById('confirmIcon').textContent = icon;
    document.getElementById('confirmTitle').textContent = title;
    document.getElementById('confirmMessage').textContent = message;
    
    // Handle input field
    const inputGroup = document.getElementById('confirmInputGroup');
    const singleInputLabel = document.getElementById('confirmInputLabel');
    const singleInputField = document.getElementById('confirmInput');
    const batchInputs = document.getElementById('batchSubmissionInputs');
    
    if (inputConfig) {
        if (inputConfig.type === 'batch_submission') {
            // Show batch submission inputs
            singleInputLabel.style.display = 'none';
            singleInputField.style.display = 'none';
            batchInputs.style.display = 'block';
            inputGroup.style.display = 'block';
            
            // Set default year to next 2-digit year (for testing next year's crop)
            const nextYear = (new Date().getFullYear() + 1).toString().slice(-2);
            document.getElementById('yearInput').value = nextYear;
            document.getElementById('trackingInput').value = '';
            
            // Focus the tracking input
            setTimeout(() => {
                document.getElementById('trackingInput').focus();
            }, 200);
        } else {
            // Show single input
            singleInputLabel.textContent = inputConfig.label;
            singleInputField.placeholder = inputConfig.placeholder || '';
            singleInputField.value = inputConfig.value || '';
            singleInputField.required = inputConfig.required || false;
            singleInputLabel.style.display = 'block';
            singleInputField.style.display = 'block';
            batchInputs.style.display = 'none';
            inputGroup.style.display = 'block';
            
            // Focus the input field after modal opens
            setTimeout(() => singleInputField.focus(), 200);
        }
    } else {
        inputGroup.style.display = 'none';
    }
    
    confirmCallback = onConfirm;
    document.getElementById('confirmModal').style.display = 'flex';
}

function validateYear(yearStr) {
    // Check if it's exactly 2 digits and numeric
    const yearPattern = /^\d{2}$/;
    return yearPattern.test(yearStr);
}

function handleConfirm() {
    const inputGroup = document.getElementById('confirmInputGroup');
    const batchInputs = document.getElementById('batchSubmissionInputs');
    
    let inputValue = null;
    
    // Get input value if input field is shown
    if (inputGroup.style.display !== 'none') {
        if (batchInputs.style.display !== 'none') {
            // Handle batch submission inputs
            const trackingNumber = document.getElementById('trackingInput').value.trim();
            const year = document.getElementById('yearInput').value.trim();
            
            // Validate year is 2 digits
            if (!validateYear(year)) {
                // Show error styling
                const yearInput = document.getElementById('yearInput');
                yearInput.classList.add('error');
                setTimeout(() => yearInput.classList.remove('error'), 3000);
                
                // Show toast error
                showToast('error', 'Invalid Year', 'Year must be exactly 2 digits (e.g., "25" for 2025).');
                return;
            }
            
            // Return both values as an object
            inputValue = {
                tracking_number: trackingNumber,
                year: year
            };
        } else {
            // Handle single input
            const inputField = document.getElementById('confirmInput');
            inputValue = inputField.value.trim();
            
            // Check if required input is empty
            if (inputField.required && !inputValue) {
                inputField.focus();
                showToast('warning', 'Required Field', 'Please fill in the required field.');
                return;
            }
        }
    }
    
    // SAVE the callback BEFORE closing the modal
    const savedCallback = confirmCallback;
    
    closeModal('confirmModal');
    
    if (savedCallback) {
        savedCallback(inputValue);
    }
}

// Populate batch dropdown with real data
function populateBatchDropdown() {
    const select = document.getElementById('batchSelect');
    select.innerHTML = '<option value="">Select Batch</option>';
    
    // Find pending batch (date is null)
    const pendingBatch = allBatches.find(b => b.status === 'pending');
    if (pendingBatch) {
        select.innerHTML += `<option value="${pendingBatch.id}">Current Batch (Pending) - ${pendingBatch.batch_number}</option>`;
    }
    
    // Add sent batches (have dates)
    const sentBatches = allBatches.filter(b => b.status === 'sent');
    sentBatches.forEach(batch => {
        const displayDate = batch.date || 'No date';
        select.innerHTML += `<option value="${batch.id}">Batch ${batch.batch_number} - Sent ${displayDate}</option>`;
    });
}

// Keyboard listener for barcode scanner
function setupKeyboardListener() {
    document.addEventListener('keydown', function(event) {
        if (!scanningActive) return;

        // Handle Enter key (end of barcode scan)
        if (event.key === 'Enter') {
            if (scanInput.trim()) {
                processScan(scanInput.trim());
                scanInput = '';
            }
            event.preventDefault();
            return;
        }

        // Accumulate scan input
        if (event.key.length === 1 || event.key === 'Backspace') {
            clearTimeout(scanTimeout);
            
            if (event.key === 'Backspace') {
                scanInput = scanInput.slice(0, -1);
            } else {
                scanInput += event.key;
            }

            // Auto-process if no input for 100ms (typical of barcode scanners)
            scanTimeout = setTimeout(() => {
                if (scanInput.trim()) {
                    processScan(scanInput.trim());
                    scanInput = '';
                }
            }, 100);
        }
    });
}

// Create new batch
function createNewBatch() {
    // Check if there's already a pending batch
    const pendingBatch = allBatches.find(b => b.status === 'pending');
    if (pendingBatch) {
        showToast('warning', 'Batch Already Pending', 
            `Batch ${pendingBatch.batch_number} is already pending. Please complete or send it before creating a new one.`);
        return;
    }
    
    document.getElementById('newBatchModal').style.display = 'flex';
}

function confirmNewBatch() {
    fetch(CREATE_NEW_BATCH_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Add new batch to local data
            const newBatch = {
                id: data.batch.id,
                batch_number: data.batch.batch_number,
                date: null, // null for pending batches
                status: 'pending',
                germinations: []
            };
            
            allBatches.unshift(newBatch); // Add to beginning
            populateBatchDropdown(); // Refresh dropdown
            
            closeModal('newBatchModal');
            
            // Auto-select the new batch
            document.getElementById('batchSelect').value = data.batch.id;
            selectBatch();
            
            showToast('success', 'Batch Created', 
                `New batch ${data.batch.batch_number} created successfully! You can now start scanning samples.`);
        } else {
            showToast('error', 'Creation Failed', `Error creating batch: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('error', 'Network Error', 'Error creating batch. Please check your connection and try again.');
    });
}

// Toggle scanning mode
function toggleScanning() {
    const button = document.getElementById('scanButton');
    
    if (!currentBatch || currentBatch.status !== 'pending') {
        showToast('warning', 'No Pending Batch', 
            'Please create or select a pending batch before starting to scan.');
        return;
    }

    scanningActive = !scanningActive;
    
    if (scanningActive) {
        button.textContent = 'Stop Scanning';
        button.className = 'btn btn-info';
        showToast('info', 'Scanner Active', 
            'Barcode scanner is now active. Start scanning samples or type barcodes manually.');
    } else {
        button.textContent = 'Start Scanning';
        button.className = 'btn btn-secondary';
        showToast('info', 'Scanner Stopped', 'Barcode scanning has been deactivated.');
    }
    
    updateUI();
}

// Process scanned barcode
function processScan(barcode) {
    if (!currentBatch || currentBatch.status !== 'pending') {
        showToast('error', 'No Pending Batch', 'No pending batch selected for scanning.');
        return;
    }

    // Look up barcode in local data
    const lotData = allLots[barcode];
    if (!lotData) {
        showToast('error', 'Barcode Not Found', `Barcode "${barcode}" was not found in the system.`);
        return;
    }

    // Check if already scanned in this batch
    if (samples.find(s => s.barcode === barcode)) {
        showToast('warning', 'Duplicate Scan', 'This sample is already in the current batch.');
        return;
    }

    // Add to local samples
    const newSample = {
        barcode: barcode,
        sku_prefix: lotData.sku_prefix,
        lot_code: lotData.lot_code,
        variety_name: lotData.variety_name,
        crop_name: lotData.crop_name,
        lot_id: lotData.lot_id,
        scan_time: new Date().toLocaleTimeString(),
        status: 'scanned' // Initial status when scanned
    };

    samples.push(newSample);
    
    // Sort by sku_prefix
    samples.sort((a, b) => a.sku_prefix.localeCompare(b.sku_prefix));
    
    // Update UI
    updateSamplesTable();
    updateUI();
    
    showToast('success', 'Sample Added', 
        `${lotData.variety_name} (${lotData.sku_prefix}) - ${lotData.lot_code} added successfully`, 2000);
}

// Submit batch to database
function submitBatch() {
    if (!currentBatch || currentBatch.status !== 'pending' || samples.length === 0) {
        showToast('warning', 'Cannot Submit', 'No pending batch with samples to submit.');
        return;
    }

    // Deactivate scanner when submitting
    if (scanningActive) {
        scanningActive = false;
        const scanButton = document.getElementById('scanButton');
        scanButton.textContent = 'Start Scanning';
        scanButton.className = 'btn btn-secondary';
        updateUI();
        showToast('info', 'Scanner Stopped', 'Scanner deactivated for batch submission.');
    }

    showConfirm(
        'Submit Batch for Testing',
        `Submit batch ${currentBatch.batch_number} with ${samples.length} samples? Please enter tracking information and the testing year.`,
        '📤',
        function(inputData) {
            // inputData will be an object with tracking_number and year
            const sampleLotIds = samples.map(s => s.lot_id);
            
            // Check if lot_ids exist
            if (sampleLotIds.includes(undefined) || sampleLotIds.includes(null)) {
                showToast('error', 'Data Error', 'Some samples are missing lot IDs. Please refresh and try again.');
                return;
            }

            const requestData = {
                batch_id: currentBatch.id,
                sample_ids: sampleLotIds,
                tracking_number: inputData.tracking_number,
                for_year: parseInt(inputData.year) // Send 2-digit year directly to match DB storage
            };

            fetch(SUBMIT_BATCH_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    const trackingMsg = inputData.tracking_number ? ` (Tracking: ${inputData.tracking_number})` : '';
                    showToast('success', 'Batch Submitted', 
                        `Batch ${currentBatch.batch_number} with ${samples.length} samples submitted for 20${inputData.year} testing!${trackingMsg}`);
                    
                    // Update sample statuses to "germ sent"
                    samples.forEach(sample => {
                        sample.status = 'germ sent';
                    });
                    
                    // Update the batch in the master allBatches array
                    const batchIndex = allBatches.findIndex(b => b.id === currentBatch.id);
                    if (batchIndex !== -1) {
                        allBatches[batchIndex].status = 'sent';
                        allBatches[batchIndex].date = new Date().toISOString().split('T')[0]; // Today's date
                        if (inputData.tracking_number) {
                            allBatches[batchIndex].tracking_number = inputData.tracking_number;
                        }
                        // Update germinations in the master array
                        allBatches[batchIndex].germinations = samples.map(s => ({
                            barcode: s.barcode,
                            sku_prefix: s.sku_prefix,
                            lot_code: s.lot_code,
                            variety_name: s.variety_name,
                            crop_name: s.crop_name,
                            germination_rate: s.germination_rate || 0 // Default to 0 if not set
                        }));
                    }
                    
                    // Update local currentBatch data
                    currentBatch.germinations = samples.map(s => ({
                        barcode: s.barcode,
                        sku_prefix: s.sku_prefix,
                        lot_code: s.lot_code,
                        variety_name: s.variety_name,
                        crop_name: s.crop_name,
                        germination_rate: s.germination_rate || 0
                    }));
                    
                    // Mark as sent with tracking number
                    currentBatch.status = 'sent';
                    if (inputData.tracking_number) {
                        currentBatch.tracking_number = inputData.tracking_number;
                    }
                    
                    // Refresh the dropdown with updated data
                    populateBatchDropdown();
                    
                    // Update the table to show new status
                    updateSamplesTable();
                    updateUI();
                } else {
                    console.error('Server returned error:', data.error);
                    showToast('error', 'Submission Failed', `Error submitting batch: ${data.error}`);
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                showToast('error', 'Network Error', 'Error submitting batch. Please check your connection and try again.');
            });
        },
        {
            type: 'batch_submission'
        }
    );
}

function selectBatch() {
    const select = document.getElementById('batchSelect');
    const batchId = select.value;
    
    if (batchId) {
        currentBatch = allBatches.find(b => b.id == batchId);
        if (currentBatch) {
            // Load samples for this batch
            samples = currentBatch.germinations.map(g => ({
                id: g.id,
                barcode: g.barcode,
                sku_prefix: g.sku_prefix,
                lot_code: g.lot_code,
                variety_name: g.variety_name,
                crop_name: g.crop_name,
                scan_time: g.scan_time || 'Previously scanned',
                germination_rate: g.germination_rate || 0,
                status: getSampleStatus(g, currentBatch.status)
            }));
            
            // NEW: Deactivate scanner if selecting a non-pending batch
            if (scanningActive && currentBatch.status !== 'pending') {
                scanningActive = false;
                const scanButton = document.getElementById('scanButton');
                scanButton.textContent = 'Start Scanning';
                scanButton.className = 'btn btn-secondary';
                showToast('info', 'Scanner Deactivated', 
                    `Scanner stopped because batch ${currentBatch.batch_number} has already been sent.`);
            }
        }
    } else {
        currentBatch = null;
        samples = [];
    }
    
    updateUI();
    updateSamplesTable();
}
// function selectBatch() {
//     const select = document.getElementById('batchSelect');
//     const batchId = select.value;
    
//     if (batchId) {
//         currentBatch = allBatches.find(b => b.id == batchId);
//         if (currentBatch) {
//             // Load samples for this batch
//             samples = currentBatch.germinations.map(g => ({
//                 id: g.id,
//                 barcode: g.barcode,
//                 sku_prefix: g.sku_prefix,
//                 lot_code: g.lot_code,
//                 variety_name: g.variety_name,
//                 crop_name: g.crop_name,
//                 scan_time: g.scan_time || 'Previously scanned',
//                 germination_rate: g.germination_rate || 0, // Default to 0 if not set
//                 status: getSampleStatus(g, currentBatch.status) // Determine status based on batch and sample data
//             }));
//         }
//     } else {
//         currentBatch = null;
//         samples = [];
//     }
    
//     updateUI();
//     updateSamplesTable();
// }

// Show batch info modal
function showBatchInfo() {
    if (!currentBatch) {
        showToast('info', 'No Batch Selected', 'Please select a batch first to view its information.');
        return;
    }

    const uniqueVarieties = [...new Set(samples.map(s => s.variety_name))];
    const uniqueCrops = [...new Set(samples.map(s => s.crop_name))];

    const content = document.getElementById('batchInfoContent');
    content.innerHTML = `
        <h3 style="margin-bottom: 15px; color: #333;">Batch Details</h3>
        <p><strong>Batch Number:</strong> ${currentBatch.batch_number}</p>
        <p><strong>Status:</strong> ${currentBatch.status === 'pending' ? 'Pending' : 'Sent'}</p>
        <p><strong>Date:</strong> ${currentBatch.date || 'Not sent yet'}</p>
        <p><strong>Tracking Number:</strong> ${currentBatch.tracking_number || 'None'}</p>
        <p><strong>Total Samples:</strong> ${samples.length}</p>
        <p><strong>Unique Varieties:</strong> ${uniqueVarieties.length}</p>
        <p><strong>Unique Crops:</strong> ${uniqueCrops.length}</p>
    `;
    
    document.getElementById('batchInfoModal').style.display = 'flex';
}

// Update samples table
function updateSamplesTable() {
    const tbody = document.getElementById('samplesTableBody');
    const emptyState = document.getElementById('emptyState');
    
    if (samples.length === 0) {
        tbody.innerHTML = '';
        emptyState.style.display = 'block';
    } else {
        emptyState.style.display = 'none';
        tbody.innerHTML = samples.map((sample, index) => {
            // Determine the status class for styling
            let statusClass = 'status-scanned';
            if (sample.status === 'completed') {
                statusClass = 'status-completed';
            } else if (sample.status === 'germ sent') {
                statusClass = 'status-sent';
            }
            
            return `
                <tr class="${index === samples.length - 1 ? 'new-scan' : ''}">
                    <td><strong>${sample.sku_prefix}</strong></td>
                    <td>${sample.lot_code}</td>
                    <td>${sample.variety_name}</td>
                    <td>${sample.crop_name}</td>
                    <td>
                        <span class="status-badge ${statusClass}">
                            ${sample.status}
                        </span>
                    </td>
                </tr>
            `;
        }).join('');
    }
}

// Update UI elements
function updateUI() {
    // Batch status
    const batchStatus = document.getElementById('batchStatus');
    const batchStatusText = document.getElementById('batchStatusText');
    const submitButton = document.getElementById('submitButton');
    
    if (currentBatch) {
        batchStatus.className = 'status-dot status-active';
        batchStatusText.textContent = `Batch ${currentBatch.batch_number} (${currentBatch.status})`;
        
        // Show submit button only for pending batches with samples
        if (currentBatch.status === 'pending' && samples.length > 0) {
            submitButton.style.display = 'inline-flex';
        } else {
            submitButton.style.display = 'none';
        }
    } else {
        batchStatus.className = 'status-dot status-inactive';
        batchStatusText.textContent = 'No batch selected';
        submitButton.style.display = 'none';
    }

    // Scanner status
    const scanStatus = document.getElementById('scanStatus');
    const scanStatusText = document.getElementById('scanStatusText');
    
    if (scanningActive) {
        scanStatus.className = 'status-dot status-scanning';
        scanStatusText.textContent = 'Scanning active';
    } else {
        scanStatus.className = 'status-dot status-inactive';
        scanStatusText.textContent = 'Inactive';
    }

    // Sample count
    document.getElementById('sampleCount').textContent = samples.length;
}

// Get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Get CSRF token for all requests
function getCSRFToken() {
    // Try to get from cookie first
    let token = getCookie('csrftoken');
    // Fallback to meta tag
    if (!token) {
        const meta = document.querySelector('meta[name="csrf-token"]');
        token = meta ? meta.getAttribute('content') : '';
    }
    return token;
}

// Setup CSRF for all fetch requests
function setupCSRFForFetch() {
    const originalFetch = window.fetch;
    window.fetch = function() {
        let config = arguments[1] || {};
        if (config.method && config.method.toUpperCase() !== 'GET') {
            config.headers = config.headers || {};
            config.headers['X-CSRFToken'] = getCSRFToken();
        }
        return originalFetch.apply(this, arguments);
    };
}

// Modal helpers
function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
    // Reset confirm callback and clear inputs if closing confirm modal
    if (modalId === 'confirmModal') {
        confirmCallback = null;
        document.getElementById('confirmInput').value = '';
        document.getElementById('trackingInput').value = '';
        document.getElementById('yearInput').value = '';
        document.getElementById('yearInput').classList.remove('error');
    }
}

// Close modals when clicking outside
document.addEventListener('click', function(event) {
    const modals = document.querySelectorAll('.modal-overlay');
    modals.forEach(modal => {
        if (event.target === modal) {
            modal.style.display = 'none';
            // Reset confirm callback if closing confirm modal
            if (modal.id === 'confirmModal') {
                confirmCallback = null;
            }
        }
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modals = document.querySelectorAll('.modal-overlay');
        modals.forEach(modal => {
            modal.style.display = 'none';
        });
        // Reset confirm callback and clear inputs
        confirmCallback = null;
        document.getElementById('confirmInput').value = '';
        document.getElementById('trackingInput').value = '';
        document.getElementById('yearInput').value = '';
        document.getElementById('yearInput').classList.remove('error');
    }
    
    // Handle Enter key in confirm modal inputs
    if (event.key === 'Enter' && (
        event.target.id === 'confirmInput' || 
        event.target.id === 'trackingInput' || 
        event.target.id === 'yearInput'
    )) {
        event.preventDefault();
        handleConfirm();
    }
});