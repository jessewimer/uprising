// ============================================================================
// GLOBAL STATE
// ============================================================================
let currentVarietyId = null;
let uploadedFile = null;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Get CSRF token from meta tag
 * @returns {string} CSRF token value
 */
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

/**
 * Clear all error messages on the page
 */
function clearErrors() {
    const errorElements = document.querySelectorAll('.error-message');
    errorElements.forEach(element => {
        element.style.display = 'none';
        element.textContent = '';
    });
}

/**
 * Display error message for a specific field
 * @param {string} fieldName - Name of the field with error
 * @param {string} message - Error message to display
 */
function showError(fieldName, message) {
    const errorElement = document.getElementById(fieldName + '_error');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
}

/**
 * Show success message temporarily
 * @param {string} elementId - ID of success message element
 */
function showSuccessMessage(elementId) {
    const successElement = document.getElementById(elementId);
    if (successElement) {
        successElement.style.display = 'block';
        setTimeout(() => {
            successElement.style.display = 'none';
        }, 3000);
    }
}

/**
 * Hide success message
 * @param {string} elementId - ID of success message element
 */
function hideSuccessMessage(elementId) {
    const successElement = document.getElementById(elementId);
    if (successElement) {
        successElement.style.display = 'none';
    }
}

// ============================================================================
// MODAL MANAGEMENT - SYSTEM SETTINGS
// ============================================================================

/**
 * Open System Settings modal
 */
function openSystemSettingsModal() {
    document.getElementById('systemSettingsModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

/**
 * Close System Settings modal
 */
function closeSystemSettingsModal() {
    document.getElementById('systemSettingsModal').classList.remove('active');
    document.body.style.overflow = 'auto';
}

// ============================================================================
// MODAL MANAGEMENT - WHOLESALE PRICE
// ============================================================================

/**
 * Open Wholesale Price modal (from System Settings)
 */
function openWholesalePriceModal() {
    closeSystemSettingsModal();
    document.getElementById('wholesalePriceModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

/**
 * Close Wholesale Price modal
 */
function closeWholesalePriceModal() {
    document.getElementById('wholesalePriceModal').classList.remove('active');
    document.body.style.overflow = 'auto';
    document.getElementById('wholesalePriceForm').reset();
    clearErrors();
    hideSuccessMessage('wholesalePriceSuccessMessage');
}

// ============================================================================
// MODAL MANAGEMENT - VARIETY
// ============================================================================

/**
 * Open Variety modal
 */
function openVarietyModal() {
    document.getElementById('varietyModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

/**
 * Close Variety modal
 */
function closeVarietyModal() {
    document.getElementById('varietyModal').classList.remove('active');
    document.body.style.overflow = 'auto';
    document.getElementById('varietyForm').reset();
    clearErrors();
    hideSuccessMessage('varietySuccessMessage');
}

// ============================================================================
// MODAL MANAGEMENT - PRODUCT
// ============================================================================

/**
 * Open Product modal with variety data
 * @param {Object} varietyData - Variety data containing sku_prefix
 */
function openProductModal(varietyData) {
    document.getElementById('product_variety').value = varietyData.sku_prefix;
    document.getElementById('productModal').classList.add('active');
    currentVarietyId = varietyData.sku_prefix;
}

/**
 * Close Product modal
 */
function closeProductModal() {
    document.getElementById('productModal').classList.remove('active');
    document.getElementById('productForm').reset();
    const skuSuffixSelect = document.getElementById('sku_suffix');
    const defaultOption = skuSuffixSelect.querySelector('option[value="pkt"]');
    if (defaultOption) {
        defaultOption.selected = true;
    }
    clearErrors();
    hideSuccessMessage('productSuccessMessage');
}

// ============================================================================
// MODAL MANAGEMENT - PRE OPENING REPORT
// ============================================================================

/**
 * Open Pre Opening Report modal
 */
function openPreOpeningReportModal() {
    document.getElementById('preOpeningReportModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

/**
 * Close Pre Opening Report modal
 */
function closePreOpeningReportModal() {
    document.getElementById('preOpeningReportModal').classList.remove('active');
    document.body.style.overflow = 'auto';
    // Reset form state
    document.getElementById('csvFileInput').value = '';
    document.getElementById('fileInfo').style.display = 'none';
    document.getElementById('processButton').disabled = true;
    uploadedFile = null;
    clearErrors();
}

/**
 * Open Report Results modal
 */
function openReportResultsModal() {
    document.getElementById('reportResultsModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

/**
 * Close Report Results modal
 */
function closeReportResultsModal() {
    document.getElementById('reportResultsModal').classList.remove('active');
    document.body.style.overflow = 'auto';
}

// ============================================================================
// FORM VALIDATION
// ============================================================================

/**
 * Validate Variety form
 * @returns {boolean} True if form is valid
 */
function validateVarietyForm() {
    clearErrors();
    let isValid = true;

    const skuPrefix = document.getElementById('sku_prefix').value.trim();
    if (!skuPrefix) {
        showError('sku_prefix', 'SKU Prefix is required');
        isValid = false;
    }

    return isValid;
}

/**
 * Validate Product form
 * @returns {boolean} True if form is valid
 */
function validateProductForm() {
    clearErrors();
    let isValid = true;

    const skuSuffix = document.getElementById('sku_suffix').value.trim();
    if (!skuSuffix) {
        showError('sku_suffix', 'SKU Suffix is required');
        isValid = false;
    }

    return isValid;
}

/**
 * Validate Wholesale Price form
 * @returns {boolean} True if form is valid
 */
function validateWholesalePriceForm() {
    clearErrors();
    let isValid = true;

    const year = document.getElementById('price_year').value;
    const price = document.getElementById('price_per_packet').value;

    if (!year || year < 0 || year > 99) {
        showError('year', 'Please enter a valid 2-digit year (0-99)');
        isValid = false;
    }

    if (!price || parseFloat(price) < 0) {
        showError('price_per_packet', 'Please enter a valid price');
        isValid = false;
    }

    return isValid;
}

// ============================================================================
// FILE UPLOAD HANDLING
// ============================================================================

/**
 * Handle CSV file upload
 * @param {Event} event - File input change event
 */
function handleFileUpload(event) {
    const file = event.target.files[0];
    clearErrors();
    
    if (file) {
        // Verify it's a CSV file
        if (!file.name.endsWith('.csv') && file.type !== 'text/csv') {
            showError('csvFile', 'Please select a valid CSV file');
            document.getElementById('processButton').disabled = true;
            uploadedFile = null;
            return;
        }
        
        // Store file and show success feedback
        uploadedFile = file;
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileInfo').style.display = 'flex';
        document.getElementById('processButton').disabled = false;
    }
}

/**
 * Process uploaded CSV file and generate report
 */
async function processCSV() {
    if (!uploadedFile) {
        alert('Please upload a CSV file first');
        return;
    }

    // Show loading state
    const processButton = document.getElementById('processButton');
    const originalText = processButton.innerHTML;
    processButton.innerHTML = '<span>⏳</span> Processing...';
    processButton.disabled = true;

    try {
        // Create FormData and append the CSV file
        const formData = new FormData();
        formData.append('csv_file', uploadedFile);
        
        // Send to backend for processing
        const response = await fetch(window.appUrls.processPreOpeningReport, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCSRFToken(),
            },
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Generate HTML report from data
            const reportHTML = generateReportHTML(data.report);
            document.getElementById('reportContent').innerHTML = reportHTML;
            
            // Close upload modal and show results
            closePreOpeningReportModal();
            openReportResultsModal();
        } else {
            alert('Error processing CSV: ' + (data.error || 'Unknown error'));
        }
        
    } catch (error) {
        console.error('Error processing CSV:', error);
        alert('Error processing CSV file: ' + error.message);
    } finally {
        processButton.innerHTML = originalText;
        processButton.disabled = false;
    }
}

/**
 * Generate HTML report from report data
 */
function generateReportHTML(report) {
    const { current_order_year, summary, products_not_in_db, products_without_germ, varieties_with_germ_but_no_inventory } = report;
    
    let html = `
        <div class="report-header">
            <h3>📊 Pre-Opening Report for 20${current_order_year}</h3>
            <div class="report-summary">
                <div class="summary-card">
                    <div class="summary-number">${summary.total_csv_products || 0}</div>
                    <div class="summary-label">Total CSV Products</div>
                </div>
                <div class="summary-card alert">
                    <div class="summary-number">${summary.total_not_in_db}</div>
                    <div class="summary-label">Not in Database</div>
                </div>
                <div class="summary-card alert">
                    <div class="summary-number">${summary.total_without_germ}</div>
                    <div class="summary-label">No Active Germination</div>
                </div>
                <div class="summary-card alert">
                    <div class="summary-number">${summary.total_germ_but_no_inv}</div>
                    <div class="summary-label">Has Germ but No Inventory</div>
                </div>
            </div>
        </div>
    `;
    
    // Section 1: Products not in database
    if (products_not_in_db.length > 0) {
        html += `
            <div class="report-section">
                <h4>❌ Products in CSV but NOT in Database (${products_not_in_db.length})</h4>
                <div class="report-table-wrapper">
                    <table class="report-table">
                        <thead>
                            <tr>
                                <th>SKU</th>
                                <th>Title</th>
                                <th>Tracker</th>
                                <th>Qty</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${products_not_in_db.map(item => `
                                <tr>
                                    <td><strong>${item.sku}</strong></td>
                                    <td>${item.title}</td>
                                    <td>${item.tracker}</td>
                                    <td>${item.qty}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    // Section 2: Products without germination
    if (products_without_germ.length > 0) {
        html += `
            <div class="report-section">
                <h4>⚠️ Tracked Products WITHOUT Active Germination for 20${current_order_year} (${products_without_germ.length})</h4>
                <div class="report-table-wrapper">
                    <table class="report-table">
                        <thead>
                            <tr>
                                <th>SKU</th>
                                <th>Title</th>
                                <th>Current Qty</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${products_without_germ.map(item => `
                                <tr>
                                    <td><strong>${item.sku}</strong></td>
                                    <td>${item.title}</td>
                                    <td>${item.qty}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    // Section 3: Varieties with germination but no inventory
    if (varieties_with_germ_but_no_inventory.length > 0) {
        html += `
            <div class="report-section">
                <h4>🔴 Varieties WITH Active Germination but PKT Product Has ≤0 Inventory (${varieties_with_germ_but_no_inventory.length})</h4>
                <div class="report-table-wrapper">
                    <table class="report-table">
                        <thead>
                            <tr>
                                <th>Variety</th>
                                <th>Name</th>
                                <th>SKU</th>
                                <th>Qty</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${varieties_with_germ_but_no_inventory.map(item => `
                                <tr>
                                    <td><strong>${item.variety}</strong></td>
                                    <td>${item.var_name}</td>
                                    <td>${item.sku}</td>
                                    <td class="negative-qty">${item.qty}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    // All clear message
    if (summary.total_not_in_db === 0 && summary.total_without_germ === 0 && summary.total_germ_but_no_inv === 0) {
        html += `
            <div class="report-section all-clear">
                <h3>✅ All Clear!</h3>
                <p>No issues found. Everything looks good for the opening!</p>
            </div>
        `;
    }
    
    return html;
}

// ============================================================================
// FORM SUBMISSIONS
// ============================================================================

/**
 * Handle Wholesale Price form submission
 */
document.getElementById('wholesalePriceForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (!validateWholesalePriceForm()) {
        return;
    }

    const formData = new FormData();
    formData.append('year', document.getElementById('price_year').value);
    formData.append('price_per_packet', document.getElementById('price_per_packet').value);

    try {
        const response = await fetch(window.appUrls.setWholesalePrice, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCSRFToken(),
            },
        });

        const data = await response.json();

        if (response.ok) {
            showSuccessMessage('wholesalePriceSuccessMessage');
            setTimeout(() => {
                closeWholesalePriceModal();
            }, 2000);
        } else {
            if (data.errors) {
                for (const [field, errors] of Object.entries(data.errors)) {
                    showError(field, errors[0]);
                }
            } else {
                alert('Error setting price: ' + (data.message || 'Unknown error'));
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error occurred. Please try again.');
    }
});

/**
 * Handle Variety form submission
 */
document.getElementById('varietyForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (!validateVarietyForm()) {
        return;
    }

    const formData = new FormData();
    const form = document.getElementById('varietyForm');
    
    for (const element of form.elements) {
        if (element.name && element.type !== 'submit') {
            if (element.type === 'checkbox') {
                formData.append(element.name, element.checked);
            } else {
                formData.append(element.name, element.value);
            }
        }
    }

    try {
        const response = await fetch(window.appUrls.addVariety, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCSRFToken(),
            },
        });

        const data = await response.json();

        if (response.ok) {
            showSuccessMessage('varietySuccessMessage');
            setTimeout(() => {
                closeVarietyModal();
                openProductModal(data.variety);
            }, 1500);
        } else {
            if (data.errors) {
                for (const [field, errors] of Object.entries(data.errors)) {
                    showError(field, errors[0]);
                }
            } else {
                alert('Error creating variety: ' + (data.message || 'Unknown error'));
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error occurred. Please try again.');
    }
});

/**
 * Handle Product form submission
 */
document.getElementById('productForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (!validateProductForm()) {
        return;
    }

    const formData = new FormData();
    const form = document.getElementById('productForm');
    
    formData.append('variety_id', currentVarietyId);
    
    for (const element of form.elements) {
        if (element.name && element.type !== 'submit' && element.name !== 'variety') {
            if (element.type === 'checkbox') {
                formData.append(element.name, element.checked);
            } else if (element.value !== '') {
                formData.append(element.name, element.value);
            }
        }
    }

    try {
        const response = await fetch(window.appUrls.addProduct, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCSRFToken(),
            },
        });

        const data = await response.json();

        if (response.ok) {
            showSuccessMessage('productSuccessMessage');
            setTimeout(() => {
                closeProductModal();
            }, 1500);
        } else {
            if (data.errors) {
                for (const [field, errors] of Object.entries(data.errors)) {
                    showError(field, errors[0]);
                }
            } else {
                alert('Error creating product: ' + (data.message || 'Unknown error'));
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error occurred. Please try again.');
    }
});

// ============================================================================
// EVENT LISTENERS - MODAL BACKDROP CLICKS
// ============================================================================

document.getElementById('systemSettingsModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeSystemSettingsModal();
    }
});

document.getElementById('wholesalePriceModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeWholesalePriceModal();
    }
});

document.getElementById('varietyModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeVarietyModal();
    }
});

document.getElementById('productModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeProductModal();
    }
});

document.getElementById('preOpeningReportModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closePreOpeningReportModal();
    }
});

document.getElementById('reportResultsModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeReportResultsModal();
    }
});

// ============================================================================
// EVENT LISTENERS - KEYBOARD SHORTCUTS
// ============================================================================

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        if (document.getElementById('systemSettingsModal').classList.contains('active')) {
            closeSystemSettingsModal();
        }
        if (document.getElementById('wholesalePriceModal').classList.contains('active')) {
            closeWholesalePriceModal();
        }
        if (document.getElementById('varietyModal').classList.contains('active')) {
            closeVarietyModal();
        }
        if (document.getElementById('productModal').classList.contains('active')) {
            closeProductModal();
        }
        if (document.getElementById('preOpeningReportModal').classList.contains('active')) {
            closePreOpeningReportModal();
        }
        if (document.getElementById('reportResultsModal').classList.contains('active')) {
            closeReportResultsModal();
        }
    }
});