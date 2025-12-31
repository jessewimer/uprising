

let allVarieties = JSON.parse(varietyDataString);
let allLotsData = JSON.parse(lotsDataString);
let availableLots = JSON.parse(lotsDataString);
let currentLotId = null;
let currentLotLowInv = false;
let lotToDelete = null;
let currentProductName = null;
let currentNotePopup = null;
let currentPackingRecordId = null;
let lastInventoryId = null;
let inventoryAction = null;
// Filter out retired lots
availableLots = availableLots.filter(lot => !lot.is_retired);
let currentProductId = null;
let currentEditProductId = null;
let selectedPrintOption = 'front_single';
let passwordCallback = null;
let passwordParams = null;
let bulkPrePackDecision = null;
let originalNotes = '';


function showPasswordPopup(callback, params) {
    passwordCallback = callback;
    passwordParams = params;
    document.getElementById('passwordInput').value = '';
    document.getElementById('passwordError').style.display = 'none';
    document.getElementById('passwordPopup').classList.add('show');
    
    // Focus on input
    setTimeout(() => {
        document.getElementById('passwordInput').focus();
    }, 100);
}

function hidePasswordPopup() {
    document.getElementById('passwordPopup').classList.remove('show');
    document.getElementById('passwordInput').value = '';
    document.getElementById('passwordError').style.display = 'none';
    passwordCallback = null;
    passwordParams = null;
}

function verifyPassword() {
    const password = document.getElementById('passwordInput').value;
    
    if (password === 'uprising') {
        console.log('Password correct!');
        console.log('Callback:', passwordCallback);
        console.log('Params:', passwordParams);
        
        // SAVE callback and params to local variables BEFORE hiding popup
        const callbackToExecute = passwordCallback;
        const paramsToPass = passwordParams;
        
        hidePasswordPopup(); // This clears passwordCallback and passwordParams
        
        // Execute the callback with saved variables
        if (callbackToExecute) {
            try {
                console.log('About to call callback...');
                callbackToExecute(paramsToPass);
                console.log('Callback executed successfully');
            } catch (error) {
                console.error('Error calling callback:', error);
            }
        }
    } else {
        document.getElementById('passwordError').style.display = 'block';
        document.getElementById('passwordInput').value = '';
        document.getElementById('passwordInput').focus();
    }
}


function styleInventoryDisplays() {
    const inventoryDisplays = document.querySelectorAll('.inventory-display');
    const today = new Date();
    const twelveMonthsAgo = new Date(today.getFullYear(), today.getMonth() - 12, today.getDate());
    
    inventoryDisplays.forEach(display => {
        const lotId = parseInt(display.dataset.lotId);
        const lotData = lotsExtraData.find(lot => lot.id === lotId);
        
        if (!lotData || lotData.is_mix) {
            return; // Skip mixes
        }
        
        const text = display.textContent.trim();
        
        if (text === '--' || text === '') {
            // No inventory
            display.innerHTML = `<span class="inventory-pill none">No inventory</span>`;
        } else if (lotData.recent_inventory) {
            // Has recent inventory data with date
            const invDateStr = lotData.recent_inventory.date; // Format: "MM/YYYY"
            const [month, year] = invDateStr.split('/');
            const invDate = new Date(2000 + parseInt(year), parseInt(month) - 1, 1);
            
            const isRecent = invDate >= twelveMonthsAgo;
            const pillClass = isRecent ? 'recent' : 'old';
            
            display.innerHTML = `<span class="inventory-pill ${pillClass}">${text}</span>`;
        } else {
            // Has inventory but no date info (older than 6 months based on view logic)
            // Assume it's old
            display.innerHTML = `<span class="inventory-pill old">${text}</span>`;
        }
    });
}


// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {

    const usageModalClose = document.getElementById('usageModalClose');
    const usageModal = document.getElementById('usageModal');
    
    if (usageModalClose) {
        usageModalClose.addEventListener('click', closeUsageModal);
    }
    
    if (usageModal) {
        usageModal.addEventListener('click', function(e) {
            if (e.target === this) closeUsageModal();
        });
    }

    // Auto-dismiss messages after 4 seconds
    const messages = document.querySelectorAll('.message');
    messages.forEach(function(message) {
        setTimeout(function() {
            message.style.animation = 'slideOutRight 0.3s ease-out forwards';
            setTimeout(function() {
                if (message.parentElement) {
                    message.remove();
                }
            }, 300);
        }, 4000); // 4 seconds delay
    });

    const passwordInput = document.getElementById('passwordInput');
    if (passwordInput) {
        passwordInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                verifyPassword();
            }
        });
    }

    setupSearch();
    setupPrintHandlers();
    reorderGrowerDropdown(); 
    initializeRetiredLotFilter(); 
    styleInventoryDisplays();
});

// Search setup
function setupSearch() {
    const searchInput = document.getElementById('varietySearch');
    const searchDropdown = document.getElementById('searchDropdown');

    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        // console.log('Searching for:', query);
        
        if (query.length < 2) {
            searchDropdown.classList.remove('show');
            return;
        }

        // Search through common_spelling, crop, and veg_type
        const matches = [];

        for (const [skuPrefix, data] of Object.entries(allVarieties)) {
            const matchesCommonSpelling = data.common_spelling && data.common_spelling.toLowerCase().includes(query);
            // const matchesCrop = data.crop && data.crop.toLowerCase().includes(query);
            const matchesCrop = data.crop && data.crop.toLowerCase().includes(query);
            
            if (matchesCommonSpelling || matchesCrop || matchesCrop) {
                matches.push([skuPrefix, data]);
            }
        }
        // // Only search through the common_spelling keys
        // const matches = [];
        
        // for (const [skuPrefix, data] of Object.entries(allVarieties)) {
        //     const matchesCommonSpelling = data.common_spelling && data.common_spelling.toLowerCase().includes(query);
            
        //     if (matchesCommonSpelling) {
        //         matches.push([skuPrefix, data]);
        //     }
        // }
        // console.log('Found matches:', matches.length);

        if (matches.length > 0) {

            searchDropdown.innerHTML = matches.map(([skuPrefix, data]) => `
                <div class="dropdown-item" onclick="selectVariety('${skuPrefix}')">
                    <div class="dropdown-variety-name">${data.var_name || data.common_spelling}</div>
                    <div class="dropdown-variety-type">${data.crop || ''}</div>
                </div>
            `).join('');
            searchDropdown.classList.add('show');
        } else {
            searchDropdown.innerHTML = '<div class="dropdown-item"><div class="dropdown-variety-name">No matches found</div></div>';
            searchDropdown.classList.add('show');
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
            searchDropdown.classList.remove('show');
        }
    });
}

function selectVariety(sku) {
    console.log('selectVariety called with sku:', sku);
    // Simply navigate to the new URL
    window.location.href = '/office/view-variety/' + sku + '/';
}


function showPrintPopup(productId, productName) {
    console.log('showPrintPopup called for:', productId, productName);
    
    // First check if Flask app is running
    checkFlaskConnection()
        .then(isFlaskRunning => {
            console.log('Flask running status:', isFlaskRunning);
            if (!isFlaskRunning) {
                showMessage('Printing app not running', 'error');
                return;
            }
            
            // Flask is running, proceed with normal print popup logic
            console.log('Proceeding with print popup checks...');
            proceedWithPrintPopupChecks(productId, productName);
        })
        .catch(error => {
            console.error('Error checking Flask connection:', error);
            showMessage('Printing app not running', 'error');
        });
}

function checkFlaskConnection() {
    console.log('Checking Flask connection...');
    return new Promise((resolve) => {
        // Set a short timeout for the health check
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            console.log('Flask health check timed out');
            controller.abort();
        }, 2000); // 2 second timeout
        
        fetch('http://localhost:5000/health', {
            method: 'GET',
            signal: controller.signal
        })
        .then(response => {
            clearTimeout(timeoutId);
            console.log('Flask health check response:', response.status, response.ok);
            // Check if the response is actually successful
            if (response.ok) {
                resolve(true);
            } else {
                resolve(false);
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            console.log('Flask health check failed:', error.message);
            resolve(false);
        });
    });
}


function proceedWithPrintPopupChecks(productId, productName) {
    console.log('proceedWithPrintPopupChecks called for:', productId);
    
    try {
        // Find the product row
        const productRow = document.querySelector(`tr[data-product-id="${productId}"]`);
        
        if (!productRow) {
            console.error('Could not find product row for ID:', productId);
            showMessage('Could not find product information', 'error');
            return;
        }
        
        // Get lot information from the display
        const lotCell = productRow.cells[1]; // Lot column is at index 1
        const lotText = lotCell.textContent.trim().replace(/\s+/g, '');
        
        console.log('Lot text from cell:', lotText);
        
        // Check 1: No lot assigned
        if (lotText === '--' || lotText === '') {
            console.log('No lot assigned, showing warning');
            document.getElementById('noLotWarning').classList.add('show');
            return;
        }

        // Find the matching lot in our data
        // const matchingLot = allLotsData.find(lot => {
        //     const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
        //     return lotDisplay === lotText;
        // });
        // Find the matching lot in our data - handle both mix lots and regular lots
        const matchingLot = allLotsData.find(lot => {
            if (isMix) {
                // For mix lots, match by lot_code
                return lot.lot_code === lotText;
            } else {
                // For regular lots, match by grower+year+harvest
                const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
                return lotDisplay === lotText;
            }
        });
        
        if (!matchingLot) {
            console.log('Could not find matching lot data');
            showMessage('Could not find lot information', 'error');
            return;
        }
        
        // Check 2: Retired lot (blocks all printing)
        if (matchingLot.is_retired) {
            console.log('Lot is retired, showing warning');
            document.getElementById('retiredLotWarning').classList.add('show');
            return;
        }
        
        // Check 3: Year mismatch checking (NEW LOGIC)
        const lotGermForYear = productRow.dataset.lotForYear; // Get lot's most recent germ for_year
        
        console.log('Year check - Packed for year:', packedForYear, 'Lot germ for_year:', lotGermForYear, 'Transition:', isTransition);
        
        // Check for front label printing options
        if (selectedPrintOption && shouldCheckForYear(selectedPrintOption)) {
            if (lotGermForYear && packedForYear) {
                const lotYear = parseInt(lotGermForYear);
                const packedYear = parseInt(packedForYear);
                
                if (isTransition) {
                    // Transition mode: lot year must be >= packed year
                    if (lotYear < packedYear) {
                        console.log('Transition mode: Lot year < packed year, showing warning');
                        showForYearMismatchWarning(packedForYear, lotGermForYear, lotText);
                        return;
                    }
                } else {
                    // Non-transition mode: lot year must equal packed year
                    if (lotYear !== packedYear) {
                        console.log('Non-transition mode: Lot year != packed year, showing warning');
                        showForYearMismatchWarning(packedForYear, lotGermForYear, lotText);
                        return;
                    }
                }
            } else {
                console.log('Missing year data for comparison');
                showMessage('Missing year information for comparison', 'error');
                return;
            }
        }
        
        // Check 4: Pending status (blocks all printing)
        const lotStatus = getLotStatus(lotText);
        if (lotStatus && lotStatus.toLowerCase() === 'pending') {
            console.log('Lot status is pending, showing warning');
            document.getElementById('pendingStatusWarning').classList.add('show');
            return;
        }
        
        // Check 5: Low inventory (asks for confirmation)
        if (matchingLot.low_inv === true || matchingLot.low_inv === 'true') {
            console.log('Low inventory, showing confirmation');
            currentProductId = productId;
            currentProductName = productName;
            document.getElementById('lowInventoryWarning').classList.add('show');
            return;
        }
        

        const lastPrintDate = productRow.dataset.lastPrintDate;
        if (lastPrintDate && lastPrintDate !== '--' && isWithinLastWeek(lastPrintDate)) {
            console.log('Recent print detected:', lastPrintDate);
            currentProductId = productId;
            currentProductName = productName;
            document.getElementById('lastPrintDateDisplay').textContent = lastPrintDate;
            document.getElementById('recentPrintWarning').classList.add('show');
            return;
        }

        // All checks passed - proceed with printing
        console.log('All checks passed, proceeding with print popup');
        proceedWithPrintPopup(productId, productName);
        
    } catch (error) {
        console.error('Error in proceedWithPrintPopupChecks:', error);
        showMessage('Error processing print request', 'error');
    }
}



// Check if a date is within the last 7 days
function isWithinLastWeek(dateString) {
    if (dateString === '--') return false;
    
    try {
        const printDate = new Date(dateString);
        const today = new Date();
        const oneWeekAgo = new Date(today.getTime() - (7 * 24 * 60 * 60 * 1000));
        
        return printDate >= oneWeekAgo && printDate <= today;
    } catch (error) {
        console.log('Error parsing date:', dateString);
        return false;
    }
}

function hideRecentPrintWarning() {
    document.getElementById('recentPrintWarning').classList.remove('show');
    currentProductId = null;
    currentProductName = null;
}

function continueRecentPrint() {
    const productId = currentProductId;
    const productName = currentProductName;
    hideRecentPrintWarning();
    proceedWithPrintPopup(productId, productName);
}

// Helper function to determine if we should check for_year for this print option
function shouldCheckForYear(printOption) {
    const frontLabelOptions = [
        'front_single',
        'front_sheet', 
        'front_back_single',
        'front_back_sheet'
    ];
    
    return frontLabelOptions.includes(printOption);
}

// Function to show the for_year mismatch warning
function showForYearMismatchWarning(currentYear, lotYear, lotCode) {
    const message = `Current year: 20${currentYear} | Lot ${lotCode} year: 20${lotYear}`;
    document.getElementById('forYearMismatchMessage').textContent = message;
    document.getElementById('forYearMismatchWarning').classList.add('show');
}

// Function to hide the for_year mismatch warning
function hideForYearMismatchWarning() {
    document.getElementById('forYearMismatchWarning').classList.remove('show');
}

function proceedWithPrintPopup(productId, productName) {
    currentProductId = productId;
    document.querySelector('.print-popup-title').innerHTML = `Print labels for<br>${productName}`;
    document.getElementById('printQuantity').value = 1;
    
    document.querySelectorAll('.print-option-btn').forEach(btn => btn.classList.remove('selected'));
    document.querySelector('[data-option="front_single"]').classList.add('selected');
    selectedPrintOption = 'front_single';
    
    // Set up the packed for year input/dropdown
    setupPackedForYearControl(productId);
    
    document.getElementById('printPopupOverlay').classList.add('show');
}


function setupPackedForYearControl(productId) {
    const productRow = document.querySelector(`tr[data-product-id="${productId}"]`);
    const lotGermForYear = productRow ? productRow.dataset.lotForYear : null;
    
    // Get the lot code to find extra data
    const lotCode = productRow ? productRow.dataset.lotCode : null;
    
    // Find if this is a next-year-only lot
    // const matchingLot = allLotsData.find(lot => {
    //     const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
    //     return lotDisplay === lotCode;
    // });
    // Find if this is a next-year-only lot - handle both mix lots and regular lots
    const matchingLot = allLotsData.find(lot => {
        if (isMix) {
            // For mix lots, match by lot_code
            return lot.lot_code === lotCode;
        } else {
            // For regular lots, match by grower+year+harvest
            const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
            return lotDisplay === lotCode;
        }
    });
    
    const lotExtraData = lotsExtraData.find(extra => extra.id === matchingLot?.id);
    const isNextYearOnly = lotExtraData?.is_next_year_only || false;
    
    const inputElement = document.getElementById('packedForYearInput');
    const selectElement = document.getElementById('packedForYearSelect');
    
    selectElement.innerHTML = '';
    
    if (isNextYearOnly) {
        // Special case: next year only lot - force next year
        const nextYear = parseInt(packedForYear) + 1;
        inputElement.value = `20${nextYear}`;
        inputElement.style.display = 'inline-block';
        selectElement.style.display = 'none';
        console.log('Next year only lot detected - forcing year', nextYear);
    } else if (!isTransition) {
        // Non-transition: show current packed year
        inputElement.value = `20${packedForYear}`;
        inputElement.style.display = 'inline-block';
        selectElement.style.display = 'none';
    } else {
        // Transition mode - existing logic
        const lotYear = lotGermForYear ? parseInt(lotGermForYear) : null;
        const packedYear = parseInt(packedForYear);
        
        if (lotYear && lotYear > packedYear) {
            selectElement.innerHTML = `
                <option value="${packedYear}">20${packedYear}</option>
                <option value="${packedYear + 1}">20${packedYear + 1}</option>
            `;
            selectElement.value = packedYear;
            selectElement.style.display = 'inline-block';
            inputElement.style.display = 'none';
        } else {
            inputElement.value = `20${packedForYear}`;
            inputElement.style.display = 'inline-block';
            selectElement.style.display = 'none';
        }
    }
}


function showProductActionsPopup(productId) {
    currentProductId = productId;
    document.getElementById('productActionsPopup').classList.add('show');
}

function hideProductActionsPopup() {
    document.getElementById('productActionsPopup').classList.remove('show');
    currentProductId = null;
}

function changeProductLot(productId) {
    hideProductActionsPopup();
    editProductLot(productId); // Your existing function
}

function editProduct(productId) {
    hideProductActionsPopup();
    showPasswordPopup(proceedWithEditProduct, productId);
}

function proceedWithEditProduct(productId) {
    console.log('proceedWithEditProduct called with:', productId); // DEBUG
    
    currentProductId = productId || currentProductId;
    
    // Get product data from the row
    const productRow = document.querySelector(`tr[data-product-id="${productId}"]`);
    
    if (!productRow) {
        showMessage('Could not find product data', 'error');
        return;
    }
    
    // Pre-fill all the form fields
    document.getElementById('editProductVariety').value = productRow.dataset.varietyName || '';
    document.getElementById('editProductSkuSuffix').value = productRow.dataset.skuSuffix || '';
    document.getElementById('editProductPkgSize').value = productRow.dataset.pkgSize || '';
    document.getElementById('editProductAltSku').value = productRow.dataset.altSku || '';
    document.getElementById('editProductLineitemName').value = productRow.dataset.lineitemName || '';
    document.getElementById('editProductRackLocation').value = productRow.dataset.rackLocation || '';
    document.getElementById('editProductEnvType').value = productRow.dataset.envType || '';
    document.getElementById('editProductEnvMultiplier').value = productRow.dataset.envMultiplier || '1';
    document.getElementById('editProductScoopSize').value = productRow.dataset.scoopSize || '';
    
    // Handle checkboxes - convert string to boolean
    document.getElementById('editProductPrintBack').checked = productRow.dataset.printBack === 'true';
    document.getElementById('editProductIsSubProduct').checked = productRow.dataset.isSubProduct === 'true';
    
    // Show the popup
    document.getElementById('editProductPopup').classList.add('show');
    document.body.classList.add('modal-open');
}









function toggleNotesEdit() {
    const display = document.getElementById('notes-display');
    const textarea = document.getElementById('notes-textarea');
    const editBtn = document.getElementById('notes-edit-btn');
    const saveBtn = document.getElementById('notes-save-btn');
    const cancelBtn = document.getElementById('notes-cancel-btn');
    
    originalNotes = textarea.value;
    
    // Hide display and edit button, show textarea and action buttons
    display.style.display = 'none';
    textarea.style.display = 'block';
    editBtn.style.display = 'none';
    saveBtn.style.display = 'inline-block';
    cancelBtn.style.display = 'inline-block';
    
    textarea.focus();
}








function checkShopifyInventory() {
    const skuPrefix = VARIETY_SKU_PREFIX;
    
    if (!skuPrefix) {
        alert('No variety SKU prefix available');
        return;
    }
    
    // Hide variety actions popup
    hideVarietyActionsPopup();
    
    // Show Shopify popup
    const shopifyPopup = document.getElementById('shopifyInventoryPopup');
    if (!shopifyPopup) {
        alert('Shopify popup element not found');
        return;
    }
    
    shopifyPopup.style.display = 'flex';
    document.getElementById('shopify-inventory-content').innerHTML = '<p>Loading Shopify inventory...</p>';
    
    // Fetch data
    fetch(`/office/api/check-shopify-inventory/${encodeURIComponent(skuPrefix)}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayShopifyResults(data);
            } else {
                document.getElementById('shopify-inventory-content').innerHTML = 
                    `<p style="color: red;">Error: ${data.error}</p>`;
            }
        })
        .catch(error => {
            document.getElementById('shopify-inventory-content').innerHTML = 
                `<p style="color: red;">Failed: ${error.message}</p>`;
        });
}


function displayShopifyResults(data) {
    const statusIcon = data.website_bulk 
        ? '<span style="color: #28a745; font-size: 20px;">✓</span>' 
        : '<span style="color: #dc3545; font-size: 20px;">✗</span>';
    
    let html = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 style="margin: 0;">Found ${data.total_found} variants with SKU prefix "${data.sku_prefix}"</h3>
            <div style="font-size: 16px; font-weight: 600;">
                Status: ${statusIcon}
            </div>
        </div>
    `;
    
    html += '<table class="usage-table">';
    html += '<thead><tr><th>Product</th><th>Variant</th><th>SKU</th><th>Inventory</th><th>Price</th></tr></thead>';
    html += '<tbody>';
    
    data.variants.forEach(variant => {
        html += '<tr>';
        html += `<td>${variant.product_title}</td>`;
        html += `<td>${variant.variant_title}</td>`;
        html += `<td>${variant.sku}</td>`;
        html += `<td>${variant.inventory_quantity}</td>`;
        html += `<td>$${variant.price}</td>`;
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    
    document.getElementById('shopify-inventory-content').innerHTML = html;
}
// function displayShopifyResults(data) {
//     let html = `<h3 style="margin-bottom: 15px;">Found ${data.total_found} variants with SKU prefix "${data.sku_prefix}"</h3>`;
//     html += '<table class="usage-table">';
//     html += '<thead><tr><th>Product</th><th>Variant</th><th>SKU</th><th>Inventory</th><th>Price</th></tr></thead>';
//     html += '<tbody>';
    
//     data.variants.forEach(variant => {
//         html += '<tr>';
//         html += `<td>${variant.product_title}</td>`;
//         html += `<td>${variant.variant_title}</td>`;
//         html += `<td>${variant.sku}</td>`;
//         html += `<td>${variant.inventory_quantity}</td>`;
//         html += `<td>$${variant.price}</td>`;
//         html += '</tr>';
//     });
    
//     html += '</tbody></table>';
    
//     document.getElementById('shopify-inventory-content').innerHTML = html;
// }

function closeShopifyInventoryPopup() {
    const popup = document.getElementById('shopifyInventoryPopup');
    if (popup) {
        popup.style.display = 'none';
    }
}

// Close Shopify popup when clicking outside
document.addEventListener('click', function(e) {
    const popup = document.getElementById('shopifyInventoryPopup');
    if (popup && e.target === popup) {
        closeShopifyInventoryPopup();
    }
});

// function checkShopifyInventory() {
//     console.log('=== START checkShopifyInventory ===');
    
//     const skuPrefix = VARIETY_SKU_PREFIX;
//     console.log('skuPrefix:', skuPrefix);
    
//     if (!skuPrefix) {
//         alert('No variety SKU prefix available');
//         return;
//     }
    
//     // Close variety actions popup - CORRECT ID!
//     const varietyPopup = document.getElementById('varietyActionsPopup');
//     console.log('varietyPopup found:', varietyPopup);
    
//     if (varietyPopup) {
//         varietyPopup.style.display = 'none';
//         console.log('Closed variety actions popup');
//     }
    
//     // Show Shopify popup
//     const shopifyPopup = document.getElementById('shopify-inventory-popup');
//     console.log('shopifyPopup found:', shopifyPopup);
    
//     if (!shopifyPopup) {
//         console.error('SHOPIFY POPUP NOT FOUND!');
//         alert('Shopify popup element not found');
//         return;
//     }
    
//     shopifyPopup.style.display = 'block';
//     console.log('Set shopifyPopup display to block');
    
//     document.getElementById('shopify-inventory-content').innerHTML = '<p>Loading Shopify inventory...</p>';
    
//     // Fetch data
//     const url = `/office/api/check-shopify-inventory/${encodeURIComponent(skuPrefix)}/`;
//     console.log('Fetching:', url);
    
//     fetch(url)
//         .then(response => response.json())
//         .then(data => {
//             console.log('Data received:', data);
//             if (data.success) {
//                 displayShopifyResults(data);
//             } else {
//                 document.getElementById('shopify-inventory-content').innerHTML = 
//                     `<p style="color: red;">Error: ${data.error}</p>`;
//             }
//         })
//         .catch(error => {
//             console.error('Fetch error:', error);
//             document.getElementById('shopify-inventory-content').innerHTML = 
//                 `<p style="color: red;">Failed: ${error.message}</p>`;
//         });
// }


// function displayShopifyResults(data) {
//     let html = `<h3>Found ${data.total_found} variants with SKU prefix "${data.sku_prefix}"</h3>`;
//     html += '<table class="usage-table">';
//     html += '<thead><tr><th>Product</th><th>Variant</th><th>SKU</th><th>Inventory</th><th>Price</th></tr></thead>';
//     html += '<tbody>';
    
//     data.variants.forEach(variant => {
//         html += '<tr>';
//         html += `<td>${variant.product_title}</td>`;
//         html += `<td>${variant.variant_title}</td>`;
//         html += `<td>${variant.sku}</td>`;
//         html += `<td>${variant.inventory_quantity}</td>`;
//         html += `<td>$${variant.price}</td>`;
//         html += '</tr>';
//     });
    
//     html += '</tbody></table>';
    
//     document.getElementById('shopify-inventory-content').innerHTML = html;
// }

// function closeShopifyInventoryPopup() {
//     document.getElementById('shopify-inventory-popup').style.display = 'none';
// }


// function checkShopifyInventory() {
//     try {
//         console.log('=== checkShopifyInventory CALLED ===');
//         console.log('VARIETY_SKU_PREFIX value:', VARIETY_SKU_PREFIX);
//         console.log('typeof VARIETY_SKU_PREFIX:', typeof VARIETY_SKU_PREFIX);
        
//         const skuPrefix = VARIETY_SKU_PREFIX;
        
//         if (!skuPrefix) {
//             console.error('STOPPING: No skuPrefix found!');
//             alert('No variety SKU prefix available');
//             return;
//         }
        
//         console.log('PASSED skuPrefix check, continuing...');
//         console.log('About to close lot-actions-popup');
        
//         // Close the variety actions popup
//         const lotActionsPopup = document.getElementById('lot-actions-popup');
//         console.log('lotActionsPopup element:', lotActionsPopup);
//         if (lotActionsPopup) {
//             lotActionsPopup.style.display = 'none';
//             console.log('Closed lot-actions-popup');
//         }
        
//         // Close the overlay if it exists
//         const overlay = document.getElementById('popup-overlay');
//         if (overlay) {
//             overlay.style.display = 'none';
//         }
        
//         console.log('About to open shopify-inventory-popup');
        
//         // Open the Shopify inventory popup
//         const shopifyPopup = document.getElementById('shopify-inventory-popup');
//         console.log('shopifyPopup element:', shopifyPopup);
        
//         if (!shopifyPopup) {
//             console.error('shopify-inventory-popup element not found!');
//             alert('Shopify popup element not found. Check HTML.');
//             return;
//         }
        
//         // Make sure popup is visible with proper styling
//         shopifyPopup.style.display = 'flex';
//         shopifyPopup.style.position = 'fixed';
//         shopifyPopup.style.zIndex = '10000';
//         shopifyPopup.style.left = '0';
//         shopifyPopup.style.top = '0';
//         shopifyPopup.style.width = '100%';
//         shopifyPopup.style.height = '100%';
//         shopifyPopup.style.backgroundColor = 'rgba(0,0,0,0.4)';
//         shopifyPopup.style.alignItems = 'center';
//         shopifyPopup.style.justifyContent = 'center';
        
//         console.log('Set popup display and styles');
        
//         const contentDiv = document.getElementById('shopify-inventory-content');
//         console.log('contentDiv:', contentDiv);
//         contentDiv.innerHTML = '<p>Loading Shopify inventory...</p>';
//         console.log('Set loading message');
        
//         const url = `/office/api/check-shopify-inventory/${encodeURIComponent(skuPrefix)}/`;
//         console.log('Fetching URL:', url);

//         fetch(url)
//             .then(response => {
//                 console.log('Response received. Status:', response.status);
//                 console.log('Response ok:', response.ok);
//                 if (!response.ok) {
//                     throw new Error(`HTTP error! status: ${response.status}`);
//                 }
//                 return response.json();
//             })
//             .then(data => {
//                 console.log('Data parsed:', data);
//                 if (data.success) {
//                     displayShopifyResults(data);
//                 } else {
//                     console.error('API returned error:', data.error);
//                     document.getElementById('shopify-inventory-content').innerHTML = 
//                         `<p style="color: red;">Error: ${data.error}</p>`;
//                 }
//             })
//             .catch(error => {
//                 console.error('Fetch error:', error);
//                 console.error('Error stack:', error.stack);
//                 document.getElementById('shopify-inventory-content').innerHTML = 
//                     `<p style="color: red;">Failed to check Shopify inventory: ${error.message}</p>`;
//             });
//     } catch (error) {
//         console.error('=== CAUGHT ERROR IN checkShopifyInventory ===');
//         console.error('Error:', error);
//         console.error('Error message:', error.message);
//         console.error('Error stack:', error.stack);
//         alert('Error: ' + error.message);
//     }
// }


// function displayShopifyResults(data) {
//     console.log('=== displayShopifyResults CALLED ===');
//     console.log('Displaying results for', data.total_found, 'variants');
    
//     let html = `<h3>Found ${data.total_found} variants with SKU prefix "${data.sku_prefix}"</h3>`;
//     html += '<table class="usage-table">';
//     html += '<thead><tr><th>Product</th><th>Variant</th><th>SKU</th><th>Inventory</th><th>Price</th></tr></thead>';
//     html += '<tbody>';
    
//     data.variants.forEach(variant => {
//         html += '<tr>';
//         html += `<td>${variant.product_title}</td>`;
//         html += `<td>${variant.variant_title}</td>`;
//         html += `<td>${variant.sku}</td>`;
//         html += `<td>${variant.inventory_quantity}</td>`;
//         html += `<td>$${variant.price}</td>`;
//         html += '</tr>';
//     });
    
//     html += '</tbody></table>';
    
//     document.getElementById('shopify-inventory-content').innerHTML = html;
// }

// function closeShopifyInventoryPopup() {
//     console.log('=== closeShopifyInventoryPopup CALLED ===');
//     document.getElementById('shopify-inventory-popup').style.display = 'none';
// }








function cancelNotesEdit() {
    const display = document.getElementById('notes-display');
    const textarea = document.getElementById('notes-textarea');
    const editBtn = document.getElementById('notes-edit-btn');
    const saveBtn = document.getElementById('notes-save-btn');
    const cancelBtn = document.getElementById('notes-cancel-btn');
    
    // Restore original value
    textarea.value = originalNotes;
    
    // Force reload to reset display to original state
    location.reload();
}




async function saveNotes() {
    const textarea = document.getElementById('notes-textarea');
    const newNotes = textarea.value;
    
    try {
        const response = await fetch(`/office/variety/${VARIETY_SKU_PREFIX}/update_notes/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ var_notes: newNotes })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            const display = document.getElementById('notes-display');
            const editBtn = document.getElementById('notes-edit-btn');
            const saveBtn = document.getElementById('notes-save-btn');
            const cancelBtn = document.getElementById('notes-cancel-btn');
            
            // Update display text
            display.innerHTML = newNotes ? newNotes.replace(/\n/g, '<br>') : 'No notes available';
            
            // Show display and edit button, hide textarea and action buttons
            display.style.display = 'block';
            textarea.style.display = 'none';
            editBtn.style.display = 'inline-block';
            saveBtn.style.display = 'none';
            cancelBtn.style.display = 'none';
            
            showMessage('Notes updated successfully', 'success');
        } else {
            showMessage('Error updating notes: ' + (data.message || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error updating notes:', error);
        showMessage('Network error occurred while saving notes', 'error');
    }
}

// Edit Variety Functions
function openEditVarietyPopup() {
    console.log('openEditVarietyPopup called');
    document.body.classList.add('modal-open');
    document.getElementById('editVarietyPopup').classList.add('show');
}

function hideEditVarietyPopup() {
    document.body.classList.remove('modal-open');
    document.getElementById('editVarietyPopup').classList.remove('show');
}

function saveVarietyChanges() {
    const formData = {
        sku_prefix: document.getElementById('editSkuPrefix').value,
        var_name: document.getElementById('editVarName').value,
        crop: document.getElementById('editCrop').value,
        common_spelling: document.getElementById('editCommonSpelling').value,
        common_name: document.getElementById('editCommonName').value,
        group: document.getElementById('editGroup').value,
        species: document.getElementById('editSpecies').value,
        subtype: document.getElementById('editSubtype').value,
        days: document.getElementById('editDays').value,
        active: document.getElementById('editActive').value === 'true',
        stock_qty: document.getElementById('editStockQty').value,
        photo_path: document.getElementById('editPhotoPath').value,
        wholesale: document.getElementById('editWholesale').value === 'true',
        ws_notes: document.getElementById('editWsNotes').value,
        ws_description: document.getElementById('editWsDescription').value,
        category: document.getElementById('editCategory').value
    };

    fetch('/office/edit-variety/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Variety updated successfully', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showMessage('Error updating variety: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });

    hideEditVarietyPopup();
}


function hideEditProductPopup() {
    document.getElementById('editProductPopup').classList.remove('show');
    document.body.classList.remove('modal-open');
}

function submitEditProduct(event) {
    event.preventDefault();
    
    const formData = new FormData();
    formData.append('product_id', currentProductId);
    formData.append('sku_suffix', document.getElementById('editProductSkuSuffix').value);
    formData.append('pkg_size', document.getElementById('editProductPkgSize').value);
    formData.append('env_type', document.getElementById('editProductEnvType').value);
    formData.append('alt_sku', document.getElementById('editProductAltSku').value);
    formData.append('lineitem_name', document.getElementById('editProductLineitemName').value);
    formData.append('rack_location', document.getElementById('editProductRackLocation').value);
    formData.append('env_multiplier', document.getElementById('editProductEnvMultiplier').value);
    formData.append('scoop_size', document.getElementById('editProductScoopSize').value);
    
    // Handle checkboxes - only append if checked
    if (document.getElementById('editProductPrintBack').checked) {
        formData.append('print_back', 'on');
    }
    if (document.getElementById('editProductIsSubProduct').checked) {
        formData.append('is_sub_product', 'on');
    }
    
    formData.append('csrfmiddlewaretoken', getCSRFToken());
    
    fetch('/office/edit-product/', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update the DOM data attributes with new values
            const productRow = document.querySelector(`tr[data-product-id="${currentProductId}"]`);
            if (productRow) {
                productRow.dataset.skuSuffix = document.getElementById('editProductSkuSuffix').value;
                productRow.dataset.pkgSize = document.getElementById('editProductPkgSize').value;
                productRow.dataset.envType = document.getElementById('editProductEnvType').value;
                productRow.dataset.altSku = document.getElementById('editProductAltSku').value;
                productRow.dataset.lineitemName = document.getElementById('editProductLineitemName').value;
                productRow.dataset.rackLocation = document.getElementById('editProductRackLocation').value;
                productRow.dataset.envMultiplier = document.getElementById('editProductEnvMultiplier').value;
                productRow.dataset.scoopSize = document.getElementById('editProductScoopSize').value;
                productRow.dataset.printBack = document.getElementById('editProductPrintBack').checked.toString();
                productRow.dataset.isSubProduct = document.getElementById('editProductIsSubProduct').checked.toString();
                
                // Also update the visible SKU suffix in the table cell
                const skuCell = productRow.querySelector('.product-sku');
                if (skuCell) {
                    skuCell.textContent = document.getElementById('editProductSkuSuffix').value || '--';
                }
            }
            
            showMessage('Product updated successfully', 'success');
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            showMessage('Error updating product: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });
    
    hideEditProductPopup();
}


function viewProductPackingHistory(productId) {
    hideProductActionsPopup();
    
    // Get product info from the row
    const productRow = document.querySelector(`tr[data-product-id="${productId}"]`);
    if (!productRow) {
        showMessage('Could not find product information', 'error');
        return;
    }
    
    // Set title
    const varietyName = productRow.dataset.varietyName || 'Unknown';
    const skuSuffix = productRow.dataset.skuSuffix || 'Unknown';
    
    // Show popup immediately
    document.getElementById('productPackingHistoryPopup').classList.add('show');
    document.body.classList.add('modal-open');
    
    // Fetch product packing history data
    fetch('/office/get-product-packing-history/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            product_id: productId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            populateProductPackingHistory(data.data);
        } else {
            showMessage('Error loading packing history: ' + (data.error || 'Unknown error'), 'error');
            hideProductPackingHistoryPopup();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
        hideProductPackingHistoryPopup();
    });
}

function hideProductPackingHistoryPopup() {
    hideNotePopup(); // Close any open note popups
    document.getElementById('productPackingHistoryPopup').classList.remove('show');
    document.body.classList.remove('modal-open');
}

function populateProductPackingHistory(data) {
    // Basic product info
    document.getElementById('productHistoryVarietyName').textContent = data.variety_name;
    document.getElementById('productHistorySkuDisplay').textContent = data.product_sku;
    
    // Populate print history
    populateProductPackingHistoryRecords(data.packing_history);
}


function populateProductPackingHistoryRecords(packingHistory) {
    const container = document.getElementById('productPackingHistoryContent');
    
    if (!packingHistory || packingHistory.length === 0) {
        container.innerHTML = '<div class="no-records">No print records found</div>';
        return;
    }
    
    // Group by for_year and sort
    const groupedByYear = {};
    
    packingHistory.forEach(pack => {
        const year = pack.for_year || 'Unknown';
        if (!groupedByYear[year]) {
            groupedByYear[year] = [];
        }
        groupedByYear[year].push(pack);
    });
    
    // Sort years (newest first) and sort records within each year by date (newest first)
    const sortedYears = Object.keys(groupedByYear).sort((a, b) => {
        if (a === 'Unknown') return 1;
        if (b === 'Unknown') return -1;
        return b.localeCompare(a);
    });
    
    let html = '';
    
    sortedYears.forEach(year => {
        // Sort records within year by date (newest first)
        const sortedRecords = groupedByYear[year].sort((a, b) => 
            new Date(b.date) - new Date(a.date)
        );
        
        // Add year header
        const displayYear = year.length === 2 ? `20${year}` : year;
        html += `
            <div class="packing-year-header">
                <h4>Printed for ${displayYear}:</h4>
            </div>
        `;
        
        // Add records for this year
        sortedRecords.forEach(pack => {
            html += `
                <div class="record-item" style="margin-left: 15px;">
                    <div class="record-main-info" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                        <div style="display: flex; align-items: center; gap: 20px; flex: 1; min-width: 0;">
                            <span class="record-date" style="min-width: 80px; flex-shrink: 0;">${pack.date}</span>
                            <div class="record-detail" style="flex-shrink: 0;">
                                <span class="record-detail-label">Qty:</span>
                                <span class="record-detail-value">${pack.qty}</span>
                            </div>
                            <div class="record-detail" style="flex-shrink: 0;">
                                <span class="record-detail-label">Lot:</span>
                                <span class="record-detail-value">${pack.lot_code}</span>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 4px; flex-shrink: 0; margin-left: 20px;">
                            <span class="edit-icon" onclick="showEditPackingRecordPopup(${pack.id}, ${pack.qty}, '${pack.date}', '${pack.lot_code}')">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </span>
                            <span class="edit-icon" style="color: #dc3545;" onclick="showDeletePackingRecordPopup(${pack.id}, '${pack.date}', '${pack.lot_code}', ${pack.qty})">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3,6 5,6 21,6"></polyline>
                                    <path d="M19,6V20a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2V6"></path>
                                    <line x1="10" y1="11" x2="10" y2="17"></line>
                                    <line x1="14" y1="11" x2="14" y2="17"></line>
                                </svg>
                            </span>
                        </div>
                    </div>
                </div>
            `;
        });
        
        // Add spacing between year groups
        if (year !== sortedYears[sortedYears.length - 1]) {
            html += '<div class="year-group-spacing"></div>';
        }
    });
    
    container.innerHTML = html;
}


// Edit Packing Record Functions
function showEditPackingRecordPopup(recordId, currentQty, date, lotCode) {
    currentPackingRecordId = recordId;
    
    document.getElementById('editPackingRecordTitle').textContent = `Edit Record: ${date} (${lotCode})`;
    document.getElementById('currentPackingQty').value = currentQty;
    document.getElementById('deductPackingQty').value = '';
    document.getElementById('deductPackingQty').max = currentQty - 1; // Can't deduct more than current - 1
    
    document.getElementById('editPackingRecordPopup').classList.add('show');
}

function hideEditPackingRecordPopup() {
    document.getElementById('editPackingRecordPopup').classList.remove('show');
    document.getElementById('editPackingRecordForm').reset();
    currentPackingRecordId = null;
}

function submitEditPackingRecord(event) {
    event.preventDefault();
    
    const currentQty = parseInt(document.getElementById('currentPackingQty').value);
    const deductAmount = parseInt(document.getElementById('deductPackingQty').value);
    const newQty = currentQty - deductAmount;
    
    if (newQty <= 0) {
        showMessage('Cannot reduce quantity to zero or below. Use delete instead.', 'error');
        return;
    }
    
    fetch('/office/edit-packing-record/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            record_id: currentPackingRecordId,
            new_qty: newQty
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Packing record updated successfully', 'success');
            // Close both popups to force user to reopen and see changes
            hideEditPackingRecordPopup();
            hideProductPackingHistoryPopup();
        } else {
            showMessage('Error updating record: ' + (data.error || 'Unknown error'), 'error');
            hideEditPackingRecordPopup();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
        hideEditPackingRecordPopup();
    });
}

// Delete Packing Record Functions
function showDeletePackingRecordPopup(recordId, date, lotCode, qty) {
    currentPackingRecordId = recordId;
    
    // Update the confirmation message with specific details
    const confirmationText = document.querySelector('#deletePackingRecordPopup p');
    confirmationText.innerHTML = `
        Are you sure you want to delete this packing record?<br>
        <strong>Date:</strong> ${date} | <strong>Lot:</strong> ${lotCode} | <strong>Qty:</strong> ${qty}<br>
        <strong>This action cannot be undone.</strong>
    `;
    
    document.getElementById('deletePackingRecordPopup').classList.add('show');
}

function hideDeletePackingRecordPopup() {
    document.getElementById('deletePackingRecordPopup').classList.remove('show');
    currentPackingRecordId = null;
}

function confirmDeletePackingRecord() {
    if (!currentPackingRecordId) {
        showMessage('No record selected', 'error');
        return;
    }
    
    fetch('/office/delete-packing-record/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            record_id: currentPackingRecordId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Packing record deleted successfully', 'success');
            // Close both popups to force user to reopen and see changes
            hideDeletePackingRecordPopup();
            hideProductPackingHistoryPopup();
        } else {
            showMessage('Error deleting record: ' + (data.error || 'Unknown error'), 'error');
            hideDeletePackingRecordPopup();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
        hideDeletePackingRecordPopup();
    });
}


function getLotStatus(lotCode) {
    console.log('getLotStatus called with lotCode:', lotCode);
    
    try {
        // Find the lot status from the lots table
        const lotRows = document.querySelectorAll('.lots-table tbody tr');
        console.log('Found lot rows:', lotRows.length);
        
        if (lotRows.length === 0) {
            console.log('No lot rows found in table');
            return null;
        }
        
        for (const row of lotRows) {
            console.log('Checking row:', row);
            const rowLotCode = row.cells[0].textContent.trim().replace(/\s+/g, '');
            console.log('Row lot code:', rowLotCode, 'comparing to:', lotCode);
            
            if (rowLotCode === lotCode) {
                console.log('Found matching row, getting status from cells[3]');
                // Status is in the 4th column (index 3)
                const status = row.cells[3].textContent.trim();
                console.log('Status found:', status);
                return status;
            }
        }
        
        console.log('No matching lot code found in table');
        return null;
        
    } catch (error) {
        console.error('Error in getLotStatus:', error);
        throw error; // Re-throw so the calling function can catch it
    }
}


function hidePendingStatusWarning() {
    document.getElementById('pendingStatusWarning').classList.remove('show');
}


// Photo popup functions
function showPhotoPopup() {
    document.getElementById('photoPopupOverlay').classList.add('show');
}

function hidePhotoPopup() {
    document.getElementById('photoPopupOverlay').classList.remove('show');
}

function hidePrintPopup() {
    document.getElementById('printPopupOverlay').classList.remove('show');
    
    // Reset button states when popup closes
    const printBtn = document.querySelector('.print-btn');
    const cancelBtn = document.querySelector('.cancel-btn');
    const popup = document.querySelector('.print-popup');
    
    if (printBtn && cancelBtn && popup) {
        printBtn.disabled = false;
        cancelBtn.disabled = false;
        printBtn.classList.remove('loading');
        popup.classList.remove('loading');
        printBtn.textContent = 'Print';
    }
    
    currentProductId = null;
}

function hideLowInventoryWarning() {
    document.getElementById('lowInventoryWarning').classList.remove('show');
    currentProductId = null;
    currentProductName = null;
}

function continuePrintDespiteLowInv() {
    const productId = currentProductId;
    const productName = currentProductName;
    hideLowInventoryWarning();
    // console.log('Continuing print despite low inventory for:', productName);
    proceedWithPrintPopup(productId, productName);
}

// function submitPrintJob() {
//     // Check for print_back mismatch before proceeding
//     if (checkPrintBackMismatch(currentProductId, selectedPrintOption)) {
//         return; // Show warning and wait for user response
//     }
    
//     // If no mismatch, proceed with the actual print
//     proceedWithActualPrint();
// }
function submitPrintJob() {
    // Check for print_back mismatch before proceeding
    if (checkPrintBackMismatch(currentProductId, selectedPrintOption)) {
        return; // Show warning and wait for user response
    }
    
    // Check if we need to prompt for bulk pre-pack
    if (shouldPromptForBulkPrePack()) {
        showBulkPrePackPrompt();
    } else {
        // No bulk pre-pack needed, proceed directly
        bulkPrePackDecision = null;
        proceedWithActualPrint();
    }
}

function shouldPromptForBulkPrePack() {
    const productRow = document.querySelector(`tr[data-product-id="${currentProductId}"]`);
    if (!productRow) return false;
    
    const skuSuffix = productRow.dataset.skuSuffix;
    
    // Only prompt if:
    // 1. sku_suffix is NOT "pkt"
    // 2. print option includes front labels (not back-only)
    const isBulkItem = skuSuffix && skuSuffix.toLowerCase() !== 'pkt';
    const isPrintingFronts = ['front_single', 'front_sheet', 'front_back_single', 'front_back_sheet'].includes(selectedPrintOption);
    
    return isBulkItem && isPrintingFronts;
}

function showBulkPrePackPrompt() {
    const quantity = parseInt(document.getElementById('printQuantity').value);
    
    // Calculate actual quantity based on print type
    let actualQty = quantity;
    if (selectedPrintOption === 'front_sheet' || selectedPrintOption === 'front_back_sheet') {
        actualQty = quantity * 30;
    }
    
    document.getElementById('bulkPrePackQty').textContent = actualQty;
    document.getElementById('bulkPrePackPrompt').classList.add('show');
}

function hideBulkPrePackPrompt() {
    document.getElementById('bulkPrePackPrompt').classList.remove('show');
}

function cancelBulkPrePackPrompt() {
    hideBulkPrePackPrompt();
    bulkPrePackDecision = null;
    // Reset print popup if needed
}

function continueWithoutBulkPrePack() {
    hideBulkPrePackPrompt();
    bulkPrePackDecision = false;
    proceedWithActualPrint();
}

function continueWithBulkPrePack() {
    hideBulkPrePackPrompt();
    bulkPrePackDecision = true;
    proceedWithActualPrint();
}

function checkPrintBackMismatch(productId, printOption) {
    const productRow = document.querySelector(`tr[data-product-id="${productId}"]`);
    if (!productRow) return false;
    
    const printBack = productRow.dataset.printBack === 'true';
    
    // Check if printing front and back options
    const printingBothSides = ['front_back_single', 'front_back_sheet'].includes(printOption);
    // Check if printing front only options
    const printingFrontOnly = ['front_single', 'front_sheet'].includes(printOption);
    
    let warningMessage = null;
    
    // Case 1: Trying to print both sides but back labels not set to print
    if (printingBothSides && !printBack) {
        warningMessage = "This product's back labels are <strong>NOT</strong> set to print.<br><br>You are trying to print <strong>front and back</strong> labels.<br><br>Are you sure you want to continue?";
    }
    // Case 2: Trying to print front only but back labels ARE set to print
    else if (printingFrontOnly && printBack) {
        warningMessage = "This product's back labels <strong>ARE</strong> set to print.<br><br>You are only printing <strong>front</strong> labels.<br><br>Are you sure you want to continue?";
    }
    
    if (warningMessage) {
        document.getElementById('printBackWarningMessage').innerHTML = warningMessage;
        document.getElementById('printBackWarning').classList.add('show');
        return true; // Mismatch found
    }
    
    return false; // No mismatch
}

function hidePrintBackWarning() {
    document.getElementById('printBackWarning').classList.remove('show');
}

function continuePrintDespiteBackMismatch() {
    hidePrintBackWarning();
    // Proceed with the actual print submission
    proceedWithActualPrint();
}



function proceedWithActualPrint() {
    const quantity = document.getElementById('printQuantity').value;
    
    if (!currentProductId || !quantity || quantity < 1) {
        showMessage('Please enter a valid quantity', 'error');
        return;
    }

    // Disable buttons and show loading state immediately
    const printBtn = document.querySelector('.print-btn');
    const cancelBtn = document.querySelector('.cancel-btn');
    const popup = document.querySelector('.print-popup');
    
    printBtn.disabled = true;
    cancelBtn.disabled = true;
    printBtn.classList.add('loading');
    popup.classList.add('loading');
    
    // Change button text to indicate loading
    const originalPrintText = printBtn.textContent;
    printBtn.textContent = 'Printing...';

    try {
        // Get the original product row
        const originalProductRow = document.querySelector(`tr[data-product-id="${currentProductId}"]`);
        if (!originalProductRow) {
            showMessage('Could not find product data', 'error');
            resetPrintButtons(printBtn, cancelBtn, popup, originalPrintText);
            return;
        }

        // Check if we need to use alt_sku
        const skuSuffix = originalProductRow.dataset.skuSuffix;
        const altSku = originalProductRow.dataset.altSku;
        const envMultiplier = originalProductRow.dataset.envMultiplier;
        
        let printData;
        let actualQuantity = parseInt(quantity);
        
        // If this is a bulk item with alt_sku and env_multiplier, use the alt_sku product data
        if (skuSuffix && skuSuffix.toLowerCase() !== 'pkt' && altSku && envMultiplier) {
            // Find the product row where the complete SKU matches alt_sku
            // Complete SKU = variety sku_prefix + product sku_suffix
            const altProductRow = Array.from(document.querySelectorAll('tr[data-product-id]')).find(row => {
                const rowCompleteSku = `${VARIETY_SKU_PREFIX}-${row.dataset.skuSuffix}`;
                return rowCompleteSku === altSku;
            });
            
            if (!altProductRow) {
                showMessage(`Could not find alt_sku product: ${altSku}`, 'error');
                resetPrintButtons(printBtn, cancelBtn, popup, originalPrintText);
                return;
            }
            
            // Use alt product data but multiply quantity by env_multiplier
            actualQuantity = parseInt(quantity) * parseInt(envMultiplier);
            printData = collectPrintData(currentProductId, actualQuantity, altProductRow);
            
            console.log(`Using alt_sku: ${altSku}, multiplied quantity: ${quantity} × ${envMultiplier} = ${actualQuantity}`);
        } else {
            // Normal printing - use original product data
            printData = collectPrintData(currentProductId, actualQuantity);
        }
        
        if (!printData) {
            showMessage('Could not collect print data', 'error');
            resetPrintButtons(printBtn, cancelBtn, popup, originalPrintText);
            return;
        }

        // Determine Flask endpoints based on print option
        const endpoints = getFlaskEndpoints(selectedPrintOption);
        
        if (endpoints.length === 0) {
            showMessage('Invalid print option selected', 'error');
            resetPrintButtons(printBtn, cancelBtn, popup, originalPrintText);
            return;
        }

        console.log('Sending to Flask:', printData);

        // Step 1: Send to Flask for printing - SEQUENTIALLY to maintain order
        let printPromise = Promise.resolve();
        
        endpoints.forEach(endpoint => {
            printPromise = printPromise.then(() => 
                fetch(`http://localhost:5000${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(printData)
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Flask endpoint ${endpoint} failed`);
                    }
                    return response;
                })
            );
        });

        printPromise
            .then(() => {
                // Step 2: Calculate bulk_pre_pack quantity if needed
                let bulkPrePackQty = 0;
                if (bulkPrePackDecision === true) {
                    bulkPrePackQty = parseInt(quantity);  // Use ORIGINAL quantity for bulk pre-pack
                    if (selectedPrintOption === 'front_sheet' || selectedPrintOption === 'front_back_sheet') {
                        bulkPrePackQty *= 30;
                    }
                }
                
                // Step 3: Record print job in Django after all printing is complete
                return fetch('/office/print-product-labels/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCSRFToken()
                    },
                    body: JSON.stringify({
                        product_id: currentProductId,  // Use ORIGINAL product ID
                        print_type: selectedPrintOption,
                        quantity: quantity,  // Use ORIGINAL quantity for record
                        packed_for_year: printData.for_year,
                        add_to_bulk_pre_pack: bulkPrePackDecision === true,
                        bulk_pre_pack_qty: bulkPrePackQty
                    })
                });
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    let message = `Successfully printed ${actualQuantity} ${selectedPrintOption.replace('_', ' ')} label(s)`;
                    if (bulkPrePackDecision === true) {
                        message += ` and added to bulk pre-pack`;
                    }
                    showMessage(message, 'success');
                    hidePrintPopup();
                    // Reset bulk pre-pack decision
                    bulkPrePackDecision = null;
                    // Refresh page after 2 seconds to show updated print count
                    setTimeout(() => {
                        window.location.href = window.location.pathname;
                    }, 2000);
                } else {
                    showMessage('Print sent but failed to record: ' + (data.error || 'Unknown error'), 'error');
                    hidePrintPopup();
                    bulkPrePackDecision = null;
                }
            })
            .catch(error => {
                console.error('Print job error:', error);
                console.log('This is the data that would be sent to Flask:', printData);
                showMessage('Printing failed: ' + error.message, 'error');
                resetPrintButtons(printBtn, cancelBtn, popup, originalPrintText);
                bulkPrePackDecision = null;
            });

    } catch (error) {
        console.error('Data collection error:', error);
        console.log('This is the data that would be sent to Flask: [Data collection failed]');
        showMessage('Failed to collect print data', 'error');
        resetPrintButtons(printBtn, cancelBtn, popup, originalPrintText);
        bulkPrePackDecision = null;
    }
}


// Helper function to reset button states
function resetPrintButtons(printBtn, cancelBtn, popup, originalText) {
    printBtn.disabled = false;
    cancelBtn.disabled = false;
    printBtn.classList.remove('loading');
    popup.classList.remove('loading');
    printBtn.textContent = originalText;
}

function collectPrintData(productId, quantity, overrideProductRow = null) {
    // Use override row if provided, otherwise find by productId
    const productRow = overrideProductRow || document.querySelector(`tr[data-product-id="${productId}"]`);
    if (!productRow) return null;
    
    // Get the selected year from either input or dropdown
    let selectedYear;
    const inputElement = document.getElementById('packedForYearInput');
    const selectElement = document.getElementById('packedForYearSelect');
    
    if (inputElement.style.display !== 'none') {
        // Using input - extract 2-digit year from "20XX" format
        selectedYear = inputElement.value.slice(-2);
    } else {
        // Using dropdown - convert selected value to 2-digit string
        const selectedValue = parseInt(selectElement.value);
        selectedYear = selectedValue.toString().padStart(2, '0');
    }
    
    return {
        quantity: parseInt(quantity),
        variety_name: productRow.dataset.varietyName,
        crop: productRow.dataset.crop,
        common_name: productRow.dataset.commonName,
        days: productRow.dataset.days,
        sku_suffix: productRow.dataset.skuSuffix,
        pkg_size: productRow.dataset.pkgSize,
        env_type: productRow.dataset.envType,
        lot_code: productRow.dataset.lotCode,
        germination: productRow.dataset.germination,
        for_year: selectedYear,
        rad_type: productRow.dataset.radType,
        desc1: productRow.dataset.desc1,
        desc2: productRow.dataset.desc2,
        desc3: productRow.dataset.desc3,
        back1: productRow.dataset.back1,
        back2: productRow.dataset.back2,
        back3: productRow.dataset.back3,
        back4: productRow.dataset.back4,
        back5: productRow.dataset.back5,
        back6: productRow.dataset.back6,
        back7: productRow.dataset.back7
    };
}

function getFlaskEndpoints(printOption) {
    const endpointMap = {
        'front_single': ['/print-single-front'],
        'front_sheet': ['/print-sheet-front'],
        'back_single': ['/print-single-back'],
        'back_sheet': ['/print-sheet-back'],
        'front_back_single': ['/print-single-back', '/print-single-front'],
        'front_back_sheet': ['/print-sheet-front', '/print-sheet-back']

    };
    
    return endpointMap[printOption] || [];
}


function showMessage(text, type = 'success') {
    // Create message container if it doesn't exist
    let container = document.querySelector('.messages-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'messages-container';
        document.body.appendChild(container);
    }
    
    // Create message element
    const message = document.createElement('div');
    message.className = `message message-${type}`;
    message.innerHTML = `
        <span class="message-text">${text}</span>
        <button class="message-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(message);
    
    // Auto-dismiss after 4 seconds
    setTimeout(function() {
        if (message.parentElement) {
            message.style.animation = 'slideOutRight 0.3s ease-out forwards';
            setTimeout(function() {
                if (message.parentElement) {
                    message.remove();
                }
            }, 300);
        }
    }, 4000);
}


// Front Labels Functions
function showEditFrontLabelsPopup() {
    document.getElementById('editFrontLabelsPopup').classList.add('show');
}

function hideEditFrontLabelsPopup() {
    document.getElementById('editFrontLabelsPopup').classList.remove('show');
}

function submitEditFrontLabels(event) {
    event.preventDefault();
    
    const labelData = {
        variety_sku: VARIETY_SKU_PREFIX,
        desc_line1: document.getElementById('editFrontLine1').value,
        desc_line2: document.getElementById('editFrontLine2').value,
        desc_line3: document.getElementById('editFrontLine3').value
    };
    
    fetch('/office/edit-front-labels/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(labelData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => Promise.reject(err));
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showMessage('Front labels updated successfully', 'success');
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            showMessage('Error updating front labels: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        if (error.error) {
            showMessage('Error updating front labels: ' + error.error, 'error');
        } else {
            console.error('Error:', error);
            showMessage('Network error occurred', 'error');
        }
    });
    
    hideEditFrontLabelsPopup();
}

// Back Labels Functions
function showEditBackLabelsPopup() {
    document.getElementById('editBackLabelsPopup').classList.add('show');
}

function hideEditBackLabelsPopup() {
    document.getElementById('editBackLabelsPopup').classList.remove('show');
}

function submitEditBackLabels(event) {
    event.preventDefault();
    
    const labelData = {
        variety_sku: VARIETY_SKU_PREFIX,
        back1: document.getElementById('editBackLine1').value,
        back2: document.getElementById('editBackLine2').value,
        back3: document.getElementById('editBackLine3').value,
        back4: document.getElementById('editBackLine4').value,
        back5: document.getElementById('editBackLine5').value,
        back6: document.getElementById('editBackLine6').value,
        back7: document.getElementById('editBackLine7').value
    };
    
    fetch('/office/edit-back-labels/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(labelData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => Promise.reject(err));
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showMessage('Back labels updated successfully', 'success');
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            showMessage('Error updating back labels: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        if (error.error) {
            showMessage('Error updating back labels: ' + error.error, 'error');
        } else {
            console.error('Error:', error);
            showMessage('Network error occurred', 'error');
        }
    });
    
    hideEditBackLabelsPopup();
}


// Filter retired lots functionality
let showRetiredLots = false;

function toggleRetiredLots() {
    const retiredRows = document.querySelectorAll('.lots-table tbody tr.retired-lot');
    const filterIcon = document.getElementById('statusFilterIcon');
    
    // If there are no retired lots, do nothing
    if (retiredRows.length === 0) {
        return;
    }
    
    showRetiredLots = !showRetiredLots;
    
    retiredRows.forEach(row => {
        if (showRetiredLots) {
            row.classList.add('show');
        } else {
            row.classList.remove('show');
        }
    });
    
    // Active state means "filtering is happening" (retired lots are hidden)
    if (showRetiredLots) {
        // Showing retired lots = no filtering = remove active state
        filterIcon.classList.remove('active');
        filterIcon.title = 'Hide retired lots';
    } else {
        // Hiding retired lots = filtering is active = add active state
        filterIcon.classList.add('active');
        filterIcon.title = 'Show retired lots';
    }
}

// Initialize retired lot filtering on page load
function initializeRetiredLotFilter() {
    // Add 'retired-lot' class to rows with retired status
    const lotsTable = document.querySelector('.lots-table tbody');
    if (lotsTable) {
        const rows = lotsTable.querySelectorAll('tr');
        rows.forEach(row => {
            const statusCell = row.querySelector('.lot-status');
            if (statusCell && statusCell.classList.contains('retired')) {
                row.classList.add('retired-lot');
            }
        });
    }
    
    // Set initial icon state based on whether retired lots exist
    const retiredRows = document.querySelectorAll('.lots-table tbody tr.retired-lot');
    const filterIcon = document.getElementById('statusFilterIcon');
    
    if (retiredRows.length > 0) {
        // There are retired lots and they're hidden by default = filtering is active
        filterIcon.classList.add('active');
        filterIcon.title = 'Show retired lots';
    } else {
        // No retired lots = no filtering needed = no active state
        filterIcon.classList.remove('active');
        filterIcon.title = 'No retired lots to filter';
    }
}




function reorderGrowerDropdown() {
    const select = document.getElementById('lotGrowerSelect');
    if (!select) return;
    
    // Get all option elements except the first one (Select grower)
    const options = Array.from(select.options).slice(1);
    
    // Sort: UO first, then alphabetically
    options.sort((a, b) => {
        if (a.text === 'UO') return -1;
        if (b.text === 'UO') return 1;
        return a.text.localeCompare(b.text);
    });
    
    // Clear existing options except the first
    while (select.options.length > 1) {
        select.removeChild(select.lastChild);
    }
    
    // Add back the sorted options
    options.forEach(option => {
        select.appendChild(option);
    });
}
// Print option handlers
function setupPrintHandlers() {
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('print-option-btn')) {
            document.querySelectorAll('.print-option-btn').forEach(btn => btn.classList.remove('selected'));
            e.target.classList.add('selected');
            selectedPrintOption = e.target.dataset.option;
        }
    });

    document.getElementById('printPopupOverlay').addEventListener('click', function(e) {
        if (e.target === this) {
            hidePrintPopup();
        }
    });

    // Photo popup click outside to close
    document.getElementById('photoPopupOverlay').addEventListener('click', function(e) {
        if (e.target === this) {
            hidePhotoPopup();
        }
    });

    // Lot selection popup click outside to close
    document.getElementById('lotSelectionPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideLotSelectionPopup();
        }
    });

    // Lot actions popup click outside to close
    document.getElementById('lotActionsPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideLotActionsPopup();
        }
    });

    // Low inventory popup click outside to close
    document.getElementById('lowInvPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideLowInvPopup();
        }
    });

    // Delete confirmation popup click outside to close
    document.getElementById('deleteConfirmPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideDeleteConfirm();
        }
    });

    // Add lot popup click outside to close
    document.getElementById('addLotPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideAddLotPopup();
        }
    });

    // Low inventory warning popup click outside to close
    document.getElementById('lowInventoryWarning').addEventListener('click', function(e) {
        if (e.target === this) {
            hideLowInventoryWarning();
        }
    });

    // No lot warning popup click outside to close
    document.getElementById('noLotWarning').addEventListener('click', function(e) {
        if (e.target === this) {
            hideNoLotWarning();
        }
    });

    // Retire lot popup click outside to close
    document.getElementById('retireLotPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideRetireLotPopup();
        }
    });

    // Stock seed popup click outside to close
    document.getElementById('stockSeedPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideStockSeedPopup();
        }
    });

    // Germination popup click outside to close
    document.getElementById('germinationPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideGerminationPopup();
        }
    });

    // Front labels popup click outside to close
    document.getElementById('editFrontLabelsPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideEditFrontLabelsPopup();
        }
    });

    // Back labels popup click outside to close
    document.getElementById('editBackLabelsPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideEditBackLabelsPopup();
        }
    });
    // Change status popup click outside to close
    document.getElementById('changeStatusPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideChangeStatusPopup();
        }
    });

    // Pending status warning popup click outside to close
    document.getElementById('pendingStatusWarning').addEventListener('click', function(e) {
        if (e.target === this) {
            hidePendingStatusWarning();
        }
    });

    // Add product popup click outside to close
    document.getElementById('addProductPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideAddProductPopup();
        }
    });

    document.getElementById('lotHistoryPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideLotHistoryPopup();
        }
    });

    document.getElementById('forYearMismatchWarning').addEventListener('click', function(e) {
        if (e.target === this) {
            hideForYearMismatchWarning();
        }
    });

    // Recent print warning popup click outside to close
    document.getElementById('recentPrintWarning').addEventListener('click', function(e) {
        if (e.target === this) {
            hideRecentPrintWarning();
        }
    });

    // Add this with your other popup event listeners
    document.getElementById('productPackingHistoryPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideProductPackingHistoryPopup();
        }
    });

    document.getElementById('editPackingRecordPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideEditPackingRecordPopup();
        }
    });

    // Delete packing record popup click outside to close
    document.getElementById('deletePackingRecordPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideDeletePackingRecordPopup();
        }
    });

    document.getElementById('reprintStockSeedPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideReprintStockSeedPopup();
        }
    });

    // Inventory popup click outside to close
    document.getElementById('inventoryPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideInventoryPopup();
        }
    });

    // Add/Overwrite Inventory popup click outside to close
    document.getElementById('addOverwriteInventoryPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideAddOverwriteInventoryPopup();
        }
    });

    // Password popup click outside to close
    document.getElementById('passwordPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hidePasswordPopup();
        }
    });

    // Close popup when clicking outside
    document.getElementById('editVarietyPopup').addEventListener('click', function(e) {
        if (e.target === this) {
            hideEditVarietyPopup();
        }
    });
}


// Updated Lot History Functions
function viewLotHistory(lotId) {
    hideLotActionsPopup();
    
    // Show popup immediately
    document.getElementById('lotHistoryPopup').classList.add('show');
    document.body.classList.add('modal-open');
    
    // Fetch lot history data
    fetch('/office/get-lot-history/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            lot_id: lotId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            populateLotHistoryPopup(data.data);
        } else {
            showMessage('Error loading lot history: ' + (data.error || 'Unknown error'), 'error');
            hideLotHistoryPopup();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
        hideLotHistoryPopup();
    });
}

function populateLotHistoryPopup(data) {
    // Basic info
    document.getElementById('historyVarietyName').textContent = data.variety_name;
    document.getElementById('historySkuDisplay').textContent = data.sku_display;
    
    // Low inventory status
    const lowInvElement = document.getElementById('historyLowInventory');
    lowInvElement.textContent = data.low_inventory ? 'Yes' : 'No';
    lowInvElement.className = `info-value lot-status-indicator ${data.low_inventory}`;
    
    // Retired status - always show
    const retiredElement = document.getElementById('historyRetiredStatus');
    const retiredDetailsSection = document.getElementById('retiredDetailsSection');
    
    if (data.is_retired) {
        retiredElement.textContent = 'Yes';
        retiredElement.className = 'info-value lot-status-indicator retired';
        retiredDetailsSection.style.display = 'block';
        
        if (data.retired_info) {
            document.getElementById('historyRetiredDate').textContent = data.retired_info.date;
            document.getElementById('historyRetiredLbs').textContent = `${data.retired_info.lbs_remaining} lbs`;
            
            const retiredNotesRow = document.getElementById('retiredNotesRow');
            if (data.retired_info.notes) {
                document.getElementById('historyRetiredNotes').textContent = data.retired_info.notes;
                retiredNotesRow.style.display = 'flex';
            } else {
                retiredNotesRow.style.display = 'none';
            }
        }
    } else {
        retiredElement.textContent = 'No';
        retiredElement.className = 'info-value lot-status-indicator false';
        retiredDetailsSection.style.display = 'none';
    }
    
    // Stock seed records
    populateStockSeedRecords(data.stock_seeds);
    
    // Inventory records
    populateInventoryRecords(data.inventory_records);
    
    // Germination records
    populateGerminationRecords(data.germination_records);
    
    // Packing history records
    populatePackingHistoryRecords(data.packing_history);
    
    // Notes
    populateNotesRecords(data.notes);
}

function populateStockSeedRecords(stockSeeds) {
    const container = document.getElementById('stockSeedContent');
    
    if (stockSeeds.length === 0) {
        container.innerHTML = '<div class="no-records">No stock seed records found</div>';
        return;
    }
    
    container.innerHTML = stockSeeds.map(stock => `
        <div class="stock-record-item">
            <div class="stock-record-main">
                <span class="record-date">${stock.date}</span>
                <div class="record-detail">
                    <span class="record-detail-label">Qty:</span>
                    <span class="record-detail-value">${stock.qty}</span>
                </div>
            </div>
            ${stock.notes ? `<div class="record-notes">${stock.notes}</div>` : ''}
        </div>
    `).join('');
}


function populateInventoryRecords(inventoryRecords) {
    const container = document.getElementById('inventoryContent');
    
    if (inventoryRecords.length === 0) {
        container.innerHTML = '<div class="no-records">No inventory records found</div>';
        return;
    }
    
    container.innerHTML = inventoryRecords.map((inv, index) => {
        const hasNote = inv.notes ? 'has-note' : '';
        const clickHandler = inv.notes ? `onclick="showNotePopup(event, ${index}, 'inv')"` : '';
        
        return `
            <div class="record-item ${hasNote}" ${clickHandler} data-note-content="${inv.notes ? inv.notes.replace(/"/g, '&quot;') : ''}">
                <div class="record-main-info">
                    <span class="record-date">${inv.date}</span>
                    <div class="record-detail">
                        <span class="record-detail-label">Weight:</span>
                        <span class="record-detail-value">${inv.weight} lbs</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}


function populateGerminationRecords(germinationRecords) {
    const container = document.getElementById('germinationContent');
    
    if (germinationRecords.length === 0) {
        container.innerHTML = '<div class="no-records">No germination records found</div>';
        return;
    }
    
    container.innerHTML = germinationRecords.map((germ, index) => {
        const hasNote = germ.notes ? 'has-note' : '';
        const clickHandler = germ.notes ? `onclick="showNotePopup(event, ${index}, 'germ')"` : '';
        
        return `
            <div class="record-item ${hasNote}" ${clickHandler} data-note-content="${germ.notes ? germ.notes.replace(/"/g, '&quot;') : ''}">
                <div class="record-main-info">
                    <span class="record-date">${germ.test_date}</span>
                    <div class="record-detail">
                        <span class="record-detail-label">Rate:</span>
                        <span class="record-detail-value">${germ.germination_rate}%</span>
                    </div>
                    <div class="record-detail">
                        <span class="record-detail-label">Year:</span>
                        <span class="record-detail-value">${germ.for_year}</span>
                    </div>
                </div>
                <span class="record-status ${germ.status}">${germ.status}</span>
            </div>
        `;
    }).join('');
}

function showNotePopup(event, index, type) {
    event.stopPropagation();
    
    // Hide any existing popup
    hideNotePopup();
    
    // Get the note content from the data attribute
    const recordItem = event.target.closest('.record-item');
    const noteContent = recordItem.dataset.noteContent;
    
    if (!noteContent) return;
    
    // Create popup element
    const popup = document.createElement('div');
    popup.className = 'note-popup show';
    popup.innerHTML = `
        <button class="note-popup-close" onclick="hideNotePopup()">&times;</button>
        <div class="note-popup-content">${noteContent}</div>
    `;
    
    // Position popup near the clicked row
    const rect = event.target.getBoundingClientRect();
    popup.style.left = `${rect.left - 150}px`; // Center popup relative to click
    popup.style.top = `${rect.bottom + 10}px`;
    
    // Ensure popup stays within viewport
    document.body.appendChild(popup);
    const popupRect = popup.getBoundingClientRect();
    
    if (popupRect.right > window.innerWidth) {
        popup.style.left = `${window.innerWidth - popupRect.width - 20}px`;
    }
    if (popupRect.left < 0) {
        popup.style.left = '20px';
    }
    if (popupRect.bottom > window.innerHeight) {
        popup.style.top = `${rect.top - popupRect.height - 10}px`;
    }
    
    currentNotePopup = popup;
    
    // Close popup when clicking outside
    setTimeout(() => {
        document.addEventListener('click', handleOutsideClick);
    }, 100);
}

function hideNotePopup() {
    if (currentNotePopup) {
        currentNotePopup.remove();
        currentNotePopup = null;
        document.removeEventListener('click', handleOutsideClick);
    }
}

function handleOutsideClick(event) {
    if (currentNotePopup && !currentNotePopup.contains(event.target)) {
        hideNotePopup();
    }
}

function hideLotHistoryPopup() {
    hideNotePopup(); // Add this line
    document.getElementById('lotHistoryPopup').classList.remove('show');
    document.body.classList.remove('modal-open');
}


function populatePackingHistoryRecords(packingHistory) {
    const container = document.getElementById('packingHistoryContent');
    
    if (packingHistory.length === 0) {
        container.innerHTML = '<div class="no-records">No packing records found</div>';
        return;
    }
    
    // Group by for_year and sort
    const groupedByYear = {};
    
    packingHistory.forEach(pack => {
        const year = pack.for_year || 'Unknown';
        if (!groupedByYear[year]) {
            groupedByYear[year] = [];
        }
        groupedByYear[year].push(pack);
    });
    
    // Sort years (newest first) and sort records within each year by date (newest first)
    const sortedYears = Object.keys(groupedByYear).sort((a, b) => {
        if (a === 'Unknown') return 1;
        if (b === 'Unknown') return -1;
        return b.localeCompare(a); // Descending order
    });
    
    let html = '';
    
    sortedYears.forEach(year => {
        // Sort records within year by date (newest first)
        const sortedRecords = groupedByYear[year].sort((a, b) => 
            new Date(b.date) - new Date(a.date)
        );
        
        // Add year header
        const displayYear = year.length === 2 ? `20${year}` : year;
        html += `
            <div class="packing-year-header">
                <h4>Packed for ${displayYear}:</h4>
            </div>
        `;
        
        // Add records for this year
        sortedRecords.forEach(pack => {
            html += `
                <div class="record-item">
                    <div class="record-main-info">
                        <span class="record-date">${pack.date}</span>
                        <div class="record-detail">
                            <span class="record-detail-label">SKU:</span>
                            <span class="record-detail-value">${pack.product_sku}</span>
                        </div>
                        <div class="record-detail">
                            <span class="record-detail-label">Qty:</span>
                            <span class="record-detail-value">${pack.qty}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        
        // Add spacing between year groups
        if (year !== sortedYears[sortedYears.length - 1]) {
            html += '<div class="year-group-spacing"></div>';
        }
    });
    
    container.innerHTML = html;
}


function populateNotesRecords(notes) {
    const container = document.getElementById('notesContent');
    
    if (notes.length === 0) {
        container.innerHTML = '<div class="no-records">No notes found</div>';
        return;
    }
    
    container.innerHTML = notes.map(note => `
        <div class="note-item">
            <div class="note-date">${note.date}</div>
            <div class="note-text">${note.note}</div>
        </div>
    `).join('');
}

function hideLotHistoryPopup() {
    document.getElementById('lotHistoryPopup').classList.remove('show');
    document.body.classList.remove('modal-open');
}

function showAddLotPopup() {
    document.getElementById('addLotPopup').classList.add('show');
}

function hideAddLotPopup() {
    document.getElementById('addLotPopup').classList.remove('show');
    document.getElementById('addLotForm').reset();
}


function submitAddLot(event) {
    event.preventDefault();
    
    const growerSelect = document.getElementById('lotGrowerSelect');
    const growerId = growerSelect.value;
    const growerCode = growerSelect.options[growerSelect.selectedIndex].getAttribute('data-grower-code'); // Get from data attribute
    const year = document.getElementById('lotYearInput').value;
    const harvest = document.getElementById('lotHarvestInput').value;
    
    // Construct the new lot code using just the grower code
    const newLotCode = `${growerCode}${year}${harvest}`;
    
    // Check if this lot already exists in the table
    const existingLots = getExistingLotsFromTable();
    
    if (existingLots.includes(newLotCode)) {
        showMessage(`Lot "${newLotCode}" already exists for this variety`, 'error');
        return; // Stop submission
    }
    
    // If we get here, the lot doesn't exist, so proceed with submission
    fetch('/office/add-lot/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            variety_sku: VARIETY_SKU_PREFIX,
            grower_id: growerId, // Still uses the grower.pk for database association
            year: year,
            harvest: harvest
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = window.location.pathname;
            localStorage.removeItem('germination_inventory_data'); 
        } else {
            showMessage('Error adding lot: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });
    
    hideAddLotPopup();
}


function getExistingLotsFromTable() {
    const existingLots = [];
    const lotRows = document.querySelectorAll('.lots-table tbody tr');
    
    lotRows.forEach(row => {
        // Get the lot code from the first column, excluding the edit icon
        const lotCell = row.cells[0];
        const lotText = lotCell.textContent.trim().replace(/\s+/g, '');
        
        // Skip empty or placeholder rows
        if (lotText && lotText !== '--') {
            existingLots.push(lotText);
        }
    });
    
    return existingLots;
}

// Edit product lot functions
function editProductLot(productId) {
    showLotSelectionPopup(productId, availableLots);
}

function showLotSelectionPopup(productId, lots) {
    const popup = document.getElementById('lotSelectionPopup');
    const lotsContainer = document.getElementById('availableLots');
    
    // Clear previous lots
    lotsContainer.innerHTML = '';
    
    // Add lots as clickable buttons
    lots.forEach(lot => {
        const button = document.createElement('button');
        button.className = 'lot-option-btn';
        
        // Different display for mix lots vs regular lots
        if (lot.is_mix) {
            button.textContent = lot.lot_code;  // e.g., "UO25A"
        } else {
            button.textContent = `${lot.grower}${lot.year}${lot.harvest}`;  // e.g., "DR25A"
        }
        
        button.onclick = () => assignLotToProduct(productId, lot.id);
        lotsContainer.appendChild(button);
    });
    
    // Add "No Lot" option
    const noLotButton = document.createElement('button');
    noLotButton.className = 'lot-option-btn no-lot';
    noLotButton.textContent = 'No Lot Assigned';
    noLotButton.onclick = () => assignLotToProduct(productId, null);
    lotsContainer.appendChild(noLotButton);
    
    popup.classList.add('show');
}

function assignLotToProduct(productId, lotId) {
    
    // Check if the "change all products" checkbox is checked
    const changeAllCheckbox = document.getElementById('changeAllProductsCheckbox');
    const changeAllProducts = changeAllCheckbox ? changeAllCheckbox.checked : false;
    
    // Determine endpoint and data based on whether this is a mix or regular variety
    const endpoint = isMix ? '/office/assign-mix-lot/' : '/office/assign-lot-to-product/';
    const lotKey = isMix ? 'mix_lot_id' : 'lot_id';
    
    const requestData = {
        product_id: productId,
        [lotKey]: lotId,
        change_all_products: changeAllProducts
    };
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show appropriate success message
            const lotType = isMix ? 'Mix lot' : 'Lot';
            const message = changeAllProducts 
                ? `${lotType} updated for all products in this variety`
                : `${lotType} updated for selected product`;
            showMessage(message, 'success');
            
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            showMessage('Error assigning lot: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });
    
    hideLotSelectionPopup();
}


function hideLotSelectionPopup() {
    document.getElementById('lotSelectionPopup').classList.remove('show');
    // Reset the checkbox when closing the popup
    const changeAllCheckbox = document.getElementById('changeAllProductsCheckbox');
    if (changeAllCheckbox) {
        changeAllCheckbox.checked = false;
    }
}

function hideLotSelectionPopup() {
    document.getElementById('lotSelectionPopup').classList.remove('show');
}

function hideRetiredLotWarning() {
    document.getElementById('retiredLotWarning').classList.remove('show');
}

function hideNoLotWarning() {
    document.getElementById('noLotWarning').classList.remove('show');
}

function showLotActionsPopup(element) {
    currentLotId = element.getAttribute('data-lot-id');
    currentLotLowInv = element.getAttribute('data-low-inv') === 'true';
    document.getElementById('lotActionsPopup').classList.add('show');
}

function hideLotActionsPopup() {
    document.getElementById('lotActionsPopup').classList.remove('show');
    currentLotId = null;
}

function editLotLowInv(lotId, currentStatus) {
    hideLotActionsPopup();
    currentLotId = lotId;
    
    // Style buttons based on current status
    const yesBtn = document.getElementById('lowInvYes');
    const noBtn = document.getElementById('lowInvNo');
    
    if (currentStatus) {
        yesBtn.style.background = 'linear-gradient(135deg, #667eea, #764ba2)';
        yesBtn.style.color = 'white';
        noBtn.style.background = '#f1f3f4';
        noBtn.style.color = '#666';
    } else {
        noBtn.style.background = 'linear-gradient(135deg, #667eea, #764ba2)';
        noBtn.style.color = 'white';
        yesBtn.style.background = '#f1f3f4';
        yesBtn.style.color = '#666';
    }
    
    document.getElementById('lowInvPopup').classList.add('show');
}

function setLotLowInv(isLowInv) {
    fetch('/office/set-lot-low-inv/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            lot_id: currentLotId,
            low_inv: isLowInv
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = window.location.pathname;
        } else {
            alert('Error updating low inventory: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Network error occurred');
    });
    
    hideLowInvPopup();
}

function retireLot(lotId) {
    hideLotActionsPopup();
    
    currentLotId = lotId;
    
    // Find the lot data to display variety and lot info
    const lot = allLotsData.find(l => l.id == lotId);
    let title = "Retire Lot";
    
    if (lot) {
        const varietyName = document.getElementById('varietyName').textContent.trim();
        
        let lotDisplay;
        if (isMix) {
            // For mix lots, show the lot_code
            lotDisplay = lot.lot_code;
        } else {
            // For regular lots, show grower/year/harvest
            lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
        }
        
        title = `Retiring ${varietyName} ${lotDisplay}`;
    }
    
    // Reset the form to clear previous values
    document.getElementById('retireLotForm').reset();
    
    // Update title and show popup
    document.getElementById('retireLotTitle').textContent = title;
    document.getElementById('retireLotPopup').classList.add('show');
    
    // Set today's date as default AFTER showing popup
    setTimeout(() => {
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('retireDateInput').value = today;
    }, 10);
}


function hideRetireLotPopup() {
    document.getElementById('retireLotPopup').classList.remove('show');
    document.getElementById('retireLotForm').reset();
}


function submitRetireLot(event) {
    event.preventDefault();
    
    const notes = document.getElementById('retireNotesInput').value;
    const retireDate = document.getElementById('retireDateInput').value;
    
    // Build request data - only include lbs_remaining for regular lots
    const requestData = {
        lot_id: currentLotId,
        is_mix: isMix,
        retire_date: retireDate,
        notes: notes
    };
    
    // Only add lbs_remaining for regular lots, not mix lots
    if (!isMix) {
        const lbsRemaining = document.getElementById('retireLbsInput').value;
        requestData.lbs_remaining = lbsRemaining;
    }
    
    console.log('Form data:', requestData);
    
    fetch('/office/retire-lot/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Response data:', data);
        if (data.success) {
            localStorage.removeItem('germination_inventory_data'); // Clear the cached data directly
            const lotType = isMix ? 'Mix lot' : 'Lot';
            showMessage(`${lotType} retired successfully`, 'success');
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 3000);
        } else {
            showMessage('Error retiring lot: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });
    
    hideRetireLotPopup();
}


function recordStockSeed(lotId) {
    hideLotActionsPopup();
    currentLotId = lotId;
    
    // Find the lot row in the table and check the Stock column
    const lotRows = document.querySelectorAll('.lots-table tbody tr');
    let hasStockSeed = false;
    
    for (const row of lotRows) {
        const editIcon = row.querySelector('.edit-icon');
        if (editIcon && editIcon.dataset.lotId === lotId.toString()) {
            // Stock is in the 6th column (index 5)
            const stockText = row.cells[5].textContent.trim();
            hasStockSeed = stockText === 'Yes';
            break;
        }
    }
    
    if (hasStockSeed) {
        showReprintStockSeedPopup(lotId);
    } else {
        showRecordStockSeedPopup(lotId);
    }
}



function showRecordStockSeedPopup(lotId) {
    // Find the lot data to display variety and lot info
    const lot = allLotsData.find(l => l.id == lotId);
    let title = "Record Stock Seed";
    
    if (lot) {
        const varietyName = document.getElementById('varietyName').textContent.trim();
        const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
        title = `Record Stock Seed<br>${varietyName} ${lotDisplay}`;
    }
    
    document.getElementById('stockSeedTitle').innerHTML = title;
    document.getElementById('stockSeedPopup').classList.add('show');
}

function showReprintStockSeedPopup(lotId) {
    document.getElementById('reprintStockSeedPopup').classList.add('show');
}

function hideReprintStockSeedPopup() {
    document.getElementById('reprintStockSeedPopup').classList.remove('show');
    currentLotId = null;
}

function reprintStockSeedLabel() {
    const lotId = currentLotId; // Capture the value immediately
    console.log('Reprinting for lot ID:', lotId);
    
    if (!lotId) {
        showMessage('No lot selected', 'error');
        return;
    }
    
    // Hide popup immediately since we have the ID captured
    hideReprintStockSeedPopup();
    
    // First check if Flask app is running
    checkFlaskConnection()
        .then(isFlaskRunning => {
            if (!isFlaskRunning) {
                showMessage('Printing app not running', 'error');
                return;
            }
            
            console.log('About to send request to Django with lot_id:', lotId);
            
            // Fetch existing stock seed data from Django
            fetch('/office/get-stock-seed-data/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({
                    lot_id: lotId // Use the captured value
                })
            })
            .then(response => {
                console.log('Django response received:', response);
                return response.json();
            })
            .then(data => {
                console.log('Django response data:', data);
                if (data.success) {
                    // Send to Flask for printing
                    const printData = {
                        variety: data.variety_name,
                        crop: data.crop,
                        lot_number: data.lot_number,
                        quantity: data.quantity
                    };
                    
                    fetch('http://localhost:5000/print-stock-seed-label', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify(printData)
                    })
                    .then(flaskResponse => {
                        if (flaskResponse.ok) {
                            showMessage('Stock seed label sent to printer successfully', 'success');
                        } else {
                            showMessage('Printing failed', 'error');
                        }
                    })
                    .catch(flaskError => {
                        console.error('Flask printing error:', flaskError);
                        showMessage('Printing failed', 'error');
                    });
                } else {
                    showMessage('Error fetching stock seed data: ' + (data.error || 'Unknown error'), 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Network error occurred', 'error');
            });
        })
        .catch(error => {
            console.error('Error checking Flask connection:', error);
            showMessage('Printing app not running', 'error');
        });
}


function hideStockSeedPopup() {
    document.getElementById('stockSeedPopup').classList.remove('show');
    document.getElementById('stockSeedForm').reset();
}

function submitStockSeed(event) {
    event.preventDefault();
    
    const qty = document.getElementById('stockSeedQtyInput').value;
    const notes = document.getElementById('stockSeedNotesInput').value;
    
    // First check if Flask app is running
    console.log('Checking Flask connection for stock seed recording...');
    checkFlaskConnection()
        .then(isFlaskRunning => {
            console.log('Flask running status for stock seed:', isFlaskRunning);
            if (!isFlaskRunning) {
                showMessage('Printing app not running - cannot print stock seed label', 'error');
                return;
            }
            
            // Flask is running, proceed with Django backend submission
            console.log('Flask healthy, proceeding with stock seed recording...');
            proceedWithStockSeedSubmission(qty, notes);
        })
        .catch(error => {
            console.error('Error checking Flask connection for stock seed:', error);
            showMessage('Printing app not running - cannot print stock seed label', 'error');
        });
}

function proceedWithStockSeedSubmission(qty, notes) {
    // Submit to Django backend first
    fetch('/office/record-stock-seed/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            lot_id: currentLotId,
            qty: qty,
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Django submission successful, now send to Flask for printing
            console.log('Stock seed recorded in Django, sending to Flask for printing...');
            
            const stockSeedPrintData = collectStockSeedPrintData(qty);
            
            if (!stockSeedPrintData) {
                showMessage('Stock seed recorded but could not collect print data', 'error');
                hideStockSeedPopup();
                return;
            }
            
            // Send to Flask for printing
            fetch('http://localhost:5000/print-stock-seed-label', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(stockSeedPrintData)
            })
            .then(flaskResponse => {
                if (flaskResponse.ok) {
                    showMessage('Stock seed recorded and label sent to printer successfully', 'success');
                } else {
                    showMessage('Stock seed recorded but printing failed', 'error');
                }
                
                setTimeout(() => {
                    window.location.href = window.location.pathname;
                }, 2000);
            })
            .catch(flaskError => {
                console.error('Flask printing error:', flaskError);
                showMessage('Stock seed recorded but printing failed', 'error');
                setTimeout(() => {
                    window.location.href = window.location.pathname;
                }, 2000);
            });
            
        } else {
            showMessage('Error recording stock seed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });
    
    hideStockSeedPopup();
}

function collectStockSeedPrintData(quantity) {
    try {
        // Get variety information
        const varietyName = document.getElementById('varietyName').textContent.trim();
        const crop = document.getElementById('varietyType').textContent.trim();
        
        // Find the lot data using currentLotId
        const lotData = allLotsData.find(lot => lot.id == currentLotId);
        
        if (!lotData) {
            console.error('Could not find lot data for ID:', currentLotId);
            return null;
        }
        
        // Construct lot number from grower + year
        const lotNumber = `${lotData.grower}${lotData.year}`;
        
        return {
            variety: varietyName,
            crop: crop,
            lot_number: lotNumber,
            quantity: quantity
        };
        
    } catch (error) {
        console.error('Error collecting stock seed print data:', error);
        return null;
    }
}


function recordInventory(lotId) {
    hideLotActionsPopup();
    currentLotId = lotId;
    
    // Find recent inventory data from pre-loaded data
    const lotExtraData = lotsExtraData.find(extra => extra.id === parseInt(lotId));
    
    if (lotExtraData && lotExtraData.recent_inventory) {
        // Show add/overwrite popup
        lastInventoryId = lotExtraData.recent_inventory.id;
        document.getElementById('lastInventoryDisplay').textContent = lotExtraData.recent_inventory.display;
        document.getElementById('addOverwriteInventoryPopup').classList.add('show');
    } else {
        // Show normal inventory popup
        showNormalInventoryPopup(lotId);
    }
}

function showNormalInventoryPopup(lotId) {
    lastInventoryId = null;
    inventoryAction = 'new';
    
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('inventoryDateInput').value = today;
    
    const lot = allLotsData.find(l => l.id == lotId);
    let title = "Record Inventory";
    
    if (lot) {
        const varietyName = document.getElementById('varietyName').textContent.trim();
        const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
        title = `Record Inventory<br>${varietyName} ${lotDisplay}`;
    }
    
    document.getElementById('inventoryTitle').innerHTML = title;
    document.getElementById('inventoryPopup').classList.add('show');
}

function hideAddOverwriteInventoryPopup() {
    document.getElementById('addOverwriteInventoryPopup').classList.remove('show');
    document.getElementById('addOverwriteInventoryForm').reset();
    lastInventoryId = null;
}

function submitAddOverwriteInventory(event) {
    event.preventDefault();
    
    const weight = document.getElementById('addOverwriteWeightInput').value;
    const action = event.submitter.value; // 'add' or 'overwrite'
    
    fetch('/office/update-inventory/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            inventory_id: lastInventoryId,
            weight: weight,
            action: action
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const actionText = action === 'add' ? 'added to' : 'overwritten';
            showMessage(`Inventory ${actionText} successfully`, 'success');
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            showMessage('Error updating inventory: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });
    
    hideAddOverwriteInventoryPopup();
}

function hideInventoryPopup() {
    document.getElementById('inventoryPopup').classList.remove('show');
    document.getElementById('inventoryForm').reset();
}

function submitInventory(event) {
    event.preventDefault();
    
    const weight = document.getElementById('inventoryWeightInput').value;
    const invDate = document.getElementById('inventoryDateInput').value;
    const notes = document.getElementById('inventoryNotesInput').value;
    
    fetch('/office/record-inventory/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            lot_id: currentLotId,
            weight: weight,
            inv_date: invDate,
            notes: notes
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => Promise.reject(err));
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showMessage('Inventory recorded successfully', 'success');
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            showMessage('Error recording inventory: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        if (error.error) {
            showMessage('Error recording inventory: ' + error.error, 'error');
        } else {
            console.error('Error:', error);
            showMessage('Network error occurred', 'error');
        }
    });
    
    hideInventoryPopup();
}


function recordGermination(lotId) {
    hideLotActionsPopup();
    currentLotId = lotId;
    
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('germinationDateInput').value = today;
    
    // Find the lot data to display variety and lot info
    const lot = allLotsData.find(l => l.id == lotId);
    let title = "Record Germination";
    
    if (lot) {
        const varietyName = document.getElementById('varietyName').textContent.trim();
        const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
        title = `Record Germination<br>${varietyName} ${lotDisplay}`;
    }
    
    document.getElementById('germinationTitle').innerHTML = title;
    document.getElementById('germinationPopup').classList.add('show');
}

function hideGerminationPopup() {
    document.getElementById('germinationPopup').classList.remove('show');
    document.getElementById('germinationForm').reset();
}

function submitGermination(event) {
    event.preventDefault();
    
    const germinationRate = document.getElementById('germinationRateInput').value;
    const testDate = document.getElementById('germinationDateInput').value;
    const notes = document.getElementById('germinationNotesInput').value;
    
    fetch('/office/record-germination/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            lot_id: currentLotId,
            germination_rate: germinationRate,
            test_date: testDate,
            notes: notes
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => Promise.reject(err));
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showMessage('Germination recorded successfully', 'success');
            localStorage.removeItem('germination_inventory_data'); // Clear the cached data directly
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            showMessage('Error recording germination: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        if (error.error) {
            showMessage('Error recording germination: ' + error.error, 'error');
        } else {
            console.error('Error:', error);
            showMessage('Network error occurred', 'error');
        }
    });
    
    hideGerminationPopup();
}


function changeLotStatus(lotId) {
    hideLotActionsPopup();
    
    // Find the current status from the lots table
    const currentStatus = getCurrentLotStatus(lotId);
    
    if (!currentStatus) {
        showMessage('Could not find lot status', 'error');
        return;
    }
    
    if (currentStatus.toLowerCase() === 'retired') {
        showMessage('Cannot change status of a retired lot', 'error');
        return;
    }
    
    // Show the status change popup
    showChangeStatusPopup(lotId, currentStatus);
}

function getCurrentLotStatus(lotId) {
    // Find the lot row in the lots table
    const lotRows = document.querySelectorAll('.lots-table tbody tr');
    
    for (const row of lotRows) {
        const editIcon = row.querySelector('.edit-icon');
        if (editIcon && editIcon.dataset.lotId === lotId.toString()) {
            // Status is in the 4th column (index 3)
            return row.cells[3].textContent.trim();
        }
    }
    
    return null;
}

function showChangeStatusPopup(lotId, currentStatus) {
    currentLotId = lotId;
    
    // Set title
    const lot = allLotsData.find(l => l.id == lotId);
    let title = "Change Lot Status";
    if (lot) {
        const varietyName = document.getElementById('varietyName').textContent.trim();
        const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
        title = `Change Status: ${varietyName} ${lotDisplay}`;
    }
    
    document.getElementById('changeStatusTitle').textContent = title;
    
    // Style buttons based on current status
    const pendingBtn = document.getElementById('pendingStatusBtn');
    const activeBtn = document.getElementById('activeStatusBtn');
    
    // Reset button classes
    pendingBtn.className = 'print-action-btn';
    activeBtn.className = 'print-action-btn';
    
    // Highlight current status
    if (currentStatus.toLowerCase() === 'pending') {
        pendingBtn.classList.add('status-btn-current');
        activeBtn.classList.add('status-btn-available');
    } else if (currentStatus.toLowerCase() === 'active') {
        activeBtn.classList.add('status-btn-current');
        pendingBtn.classList.add('status-btn-available');
    }
    
    document.getElementById('changeStatusPopup').classList.add('show');
}

function hideChangeStatusPopup() {
    document.getElementById('changeStatusPopup').classList.remove('show');
    currentLotId = null;
}

function setLotStatus(newStatus) {
    if (!currentLotId) {
        showMessage('No lot selected', 'error');
        return;
    }
    
    fetch('/office/change-lot-status/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            lot_id: currentLotId,
            status: newStatus
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`Lot status changed to ${newStatus}`, 'success');
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            showMessage('Error changing status: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });
    
    hideChangeStatusPopup();
}

// function viewLotUsage(lotId) {
//     hideLotActionsPopup();
//     console.log('View usage for lot:', lotId);
//     showMessage('View Usage functionality coming soon', 'success');
//     // TODO: Implement usage view popup
// }


// Variety Actions Popup
function showVarietyActionsPopup() {
    document.getElementById('varietyActionsPopup').classList.add('show');
}

function hideVarietyActionsPopup() {
    document.getElementById('varietyActionsPopup').classList.remove('show');
}

function editVarietyWithPassword() {
    hideVarietyActionsPopup();
    showPasswordPopup(openEditVarietyPopup, null);
}


// Close modal event listeners
document.getElementById('usageModalClose').addEventListener('click', closeUsageModal);
document.getElementById('usageModal').addEventListener('click', function(e) {
    if (e.target === this) closeUsageModal();
});

function closeUsageModal() {
    document.getElementById('usageModal').style.display = 'none';
}

function viewVarietyUsage() {
    console.log('viewVarietyUsage called');
    hideVarietyActionsPopup();
    
    const varietyName = document.getElementById('varietyName').textContent.trim();
    console.log('Variety name:', varietyName);
    
    const usageModal = document.getElementById('usageModal');
    console.log('Usage modal element:', usageModal);
    
    if (!usageModal) {
        console.error('Usage modal not found in DOM!');
        return;
    }
    
    const usageModalTitle = document.getElementById('usageModalTitle');
    console.log('Usage modal title element:', usageModalTitle);
    
    if (usageModalTitle) {
        usageModalTitle.textContent = `${varietyName}`;
    }
    
    usageModal.style.display = 'flex';
    console.log('Modal display set to flex, should be visible now');
    
    // Reset inventory section
    const inventorySection = document.getElementById('inventorySection');
    const usageSection = document.getElementById('usageSection');
    const usageLoading = document.getElementById('usageLoading');
    const usageContent = document.getElementById('usageContent');
    const usageEmpty = document.getElementById('usageEmpty');
    
    console.log('Modal elements:', {
        inventorySection,
        usageSection,
        usageLoading,
        usageContent,
        usageEmpty
    });
    
    if (inventorySection) inventorySection.style.display = 'none';
    if (usageSection) usageSection.style.display = 'none';
    if (usageLoading) usageLoading.style.display = 'block';
    if (usageContent) usageContent.style.display = 'none';
    if (usageEmpty) usageEmpty.style.display = 'none';
    
    const url = `/office/variety-usage/${VARIETY_SKU_PREFIX}/`;
    console.log('Fetching from:', url);
    
    fetch(url, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => {
        console.log('Fetch response:', response);
        return response.json();
    })
    .then(data => {
        console.log('Fetch data:', data);
        if (data.success) {
            // Show inventory section
            if (data.lot_inventory_data) {
                console.log('Populating inventory data');
                populateInventoryData(data.lot_inventory_data);
            }
            
            // Show usage section
            if (usageSection) usageSection.style.display = 'block';
            
            if (data.usage_data && data.usage_data.total_lbs > 0) {
                console.log('Populating usage data');
                populateUsageData(data.usage_data);
            } else {
                console.log('No usage data, showing empty state');
                if (usageLoading) usageLoading.style.display = 'none';
                if (usageEmpty) usageEmpty.style.display = 'block';
            }
        } else {
            console.error('Fetch unsuccessful:', data.error);
            if (usageLoading) usageLoading.style.display = 'none';
            if (usageEmpty) usageEmpty.style.display = 'block';
        }
    })
    .catch(error => {
        console.error('Usage fetch error:', error);
        if (usageLoading) usageLoading.style.display = 'none';
        if (usageEmpty) usageEmpty.style.display = 'block';
    });
}

function populateUsageData(usageData) {
    document.getElementById('usageLoading').style.display = 'none';
    document.getElementById('usageContent').style.display = 'block';
    
    // Populate summary stats
    document.getElementById('usageSeasonRange').textContent = usageData.display_year;
    document.getElementById('usageTotalLbs').textContent = `${usageData.total_lbs.toFixed(2)}`;
    document.getElementById('usageLotCount').textContent = usageData.lot_count;
    
    // Check if we need to show "ran out of seed" warning
    const usageContent = document.getElementById('usageContent');
    let existingWarning = usageContent.querySelector('.ran-out-warning');
    
    // Remove existing warning if present
    if (existingWarning) {
        existingWarning.remove();
    }
    
    // Add warning if they ran out of seed during the season
    if (usageData.ran_out_of_seed) {
        const warning = document.createElement('div');
        warning.className = 'ran-out-warning';
        warning.style.cssText = 'margin: 20px 0 15px 0; padding: 12px; background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; text-align: center;';
        warning.innerHTML = `
            <strong style="color: #856404;">⚠️ Note:</strong>
            <span style="color: #856404;"> All lots were depleted during the ${usageData.display_year} sales season. Usage numbers may not reflect actual demand.</span>
        `;
        
        // Insert warning BETWEEN usage-summary and usage-details
        const usageSummary = usageContent.querySelector('.usage-summary');
        const usageDetails = usageContent.querySelector('.usage-details');
        
        if (usageSummary && usageDetails) {
            // Insert after summary, before details
            usageSummary.parentNode.insertBefore(warning, usageDetails);
        } else if (usageSummary) {
            // No details element, just insert after summary
            usageSummary.after(warning);
        } else {
            // Fallback: append to usageContent
            usageContent.appendChild(warning);
        }
    }
    

    // Populate lot details table
    const tbody = document.getElementById('usageLotTableBody');
    tbody.innerHTML = '';

    usageData.lots.forEach(lot => {
        const row = document.createElement('tr');
        
        // Apply styling for retired OR depleted lots
        if (lot.retired || lot.depleted_not_retired) {
            row.className = 'usage-retired-row';
        }
        
        // Determine the label to display
        let lotLabel = lot.lot_code;
        if (lot.depleted_not_retired) {
            lotLabel += ' (depleted, not retired)';
        } else if (lot.retired) {
            lotLabel += ' (retired)';
        }
        
        row.innerHTML = `
            <td>${lotLabel}</td>
            <td>${lot.start_weight.toFixed(2)}</td>
            <td>${lot.end_weight.toFixed(2)}</td>
            <td class="usage-amount">${lot.usage.toFixed(2)}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function populateInventoryData(inventoryData) {
    const section = document.getElementById('inventorySection');
    const tbody = document.getElementById('inventoryTableBody');
    const emptyState = document.getElementById('inventoryEmpty');
    const table = document.querySelector('.inventory-table');
    const legend = document.getElementById('inventoryLegend');
    
    section.style.display = 'block';
    
    if (!inventoryData.lots || inventoryData.lots.length === 0) {
        table.style.display = 'none';
        emptyState.style.display = 'block';
        if (legend) legend.style.display = 'none';
        return;
    }
    
    table.style.display = 'table';
    emptyState.style.display = 'none';
    
    // Update year headers
    const years = inventoryData.years;
    document.getElementById('germYear1Header').textContent = years[0];
    document.getElementById('germYear2Header').textContent = years[1];
    document.getElementById('germYear3Header').textContent = years[2];
    
    // Clear tbody
    tbody.innerHTML = '';
    
    // Track if we have any pending germs
    let hasPendingGerms = false;
    
    // Populate rows
    inventoryData.lots.forEach(lot => {
        const row = document.createElement('tr');
        
        // Lot code cell
        const lotCell = document.createElement('td');
        lotCell.className = 'inventory-lot-cell';
        lotCell.textContent = lot.lot_code;
        row.appendChild(lotCell);
        
        // Germination cells for each year
        years.forEach(year => {
            const germCell = document.createElement('td');
            germCell.className = 'inventory-germ-cell';
            
            const germData = lot.germ_data[year];
            if (germData) {
                const germRate = germData.rate;
                const status = germData.status;
                const hasTestDate = germData.has_test_date;
                
                // Track pending germs
                if (!hasTestDate) {
                    hasPendingGerms = true;
                }
                
                // Create germ display with color
                const germDiv = document.createElement('div');
                germDiv.className = 'germ-display';
                
                // Get color class based on rate
                let colorClass = 'germ-color-default';
                if (germRate >= 85) colorClass = 'germ-color-high';
                else if (germRate >= 70) colorClass = 'germ-color-medium';
                else if (germRate >= 50) colorClass = 'germ-color-low';
                else colorClass = 'germ-color-very-low';
                
                germDiv.innerHTML = `
                    <span class="germ-rate ${colorClass}">${germRate}%</span>
                    ${!hasTestDate ? '<span class="germ-pending">*</span>' : ''}
                `;
                
                germCell.appendChild(germDiv);
            } else {
                germCell.textContent = '--';
            }
            
            row.appendChild(germCell);
        });
        
        // Inventory cell
        const invCell = document.createElement('td');
        invCell.className = 'inventory-weight-cell';
        if (lot.inventory > 0) {
            invCell.innerHTML = `
                <span class="inventory-weight">${lot.inventory.toFixed(2)}</span>
   
            `;
        } else {
            invCell.textContent = '--';
        }
        row.appendChild(invCell);
        
        tbody.appendChild(row);
    });
    
    // Show/hide legend based on whether we have pending germs
    if (legend) {
        legend.style.display = hasPendingGerms ? 'inline' : 'none';
    }
    
    // Update total
    document.getElementById('inventoryTotal').textContent = 
        `${inventoryData.total_inventory.toFixed(2)}`;
}


function deleteLot(lotId) {
    hideLotActionsPopup();
    showPasswordPopup(proceedWithDeleteLot, lotId);
}


function proceedWithDeleteLot(lotId) {
    console.log('proceedWithDeleteLot called with:', lotId);
    lotToDelete = lotId;
    
    // Find the lot data
    const lot = allLotsData.find(l => l.id == lotId);
    const varietyName = document.getElementById('varietyName').textContent.trim();
    
    // Construct lot display (grower + year + harvest)
    let lotDisplay = '--';
    if (lot && lot.grower && lot.year) {
        lotDisplay = `${lot.grower}${lot.year}${lot.harvest || ''}`;
    }
    
    // Update the confirmation message
    const confirmationText = document.querySelector('#deleteConfirmPopup p');
    confirmationText.innerHTML = `
        Are you sure you want to delete this lot?<br>
        <strong>Variety:</strong> ${varietyName}<br>
        <strong>Lot:</strong> ${lotDisplay}<br>
        <strong>This action cannot be undone.</strong>
    `;
    
    // Show the popup
    const deletePopup = document.getElementById('deleteConfirmPopup');
    deletePopup.classList.remove('show');
    
    setTimeout(() => {
        deletePopup.classList.add('show');
        console.log('Delete confirmation popup shown');
    }, 10);
}

function confirmDeleteLot() {
    if (lotToDelete) {
        // TODO: Make API call to delete the lot
        fetch('/office/delete-lot/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                lot_id: lotToDelete
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = window.location.pathname;
            } else {
                alert('Error deleting lot: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Network error occurred');
        });
    }
    hideDeleteConfirm();
}

function hideDeleteConfirm() {
    document.getElementById('deleteConfirmPopup').classList.remove('show');
    lotToDelete = null;
}
function hideLowInvPopup() {
    document.getElementById('lowInvPopup').classList.remove('show');
    currentLotId = null;
}

function findLotById(lotId) {
    return allLotsData.find(lot => lot.id == lotId);
}

function showAddProductPopup() {
    showPasswordPopup(proceedWithAddProduct, null);
}

function proceedWithAddProduct() {
    document.body.classList.add('modal-open');
    document.getElementById('addProductPopup').classList.add('show');
}

function hideAddProductPopup() {
    document.body.classList.remove('modal-open');
    document.getElementById('addProductPopup').classList.remove('show');
    document.getElementById('addProductForm').reset();
}

function submitAddProduct(event) {
    event.preventDefault();
    
    const formData = new FormData();
    formData.append('variety_id', VARIETY_SKU_PREFIX);
    formData.append('sku_suffix', document.getElementById('productSkuSuffix').value);
    formData.append('pkg_size', document.getElementById('productPkgSize').value);
    formData.append('env_type', document.getElementById('productEnvType').value);
    formData.append('alt_sku', document.getElementById('productAltSku').value);
    formData.append('lineitem_name', document.getElementById('productLineitemName').value);
    formData.append('rack_location', document.getElementById('productRackLocation').value);
    formData.append('env_multiplier', document.getElementById('productEnvMultiplier').value);
    // formData.append('label', document.getElementById('productLabel').value);
    // formData.append('num_printed', document.getElementById('productNumPrinted').value);
    // formData.append('num_printed_next_year', document.getElementById('productNumPrintedNextYear').value);
    formData.append('scoop_size', document.getElementById('productScoopSize').value);
    // formData.append('bulk_pre_pack', document.getElementById('productBulkPrePack').value);
    formData.append('print_back', document.getElementById('productPrintBack').checked);
    formData.append('is_sub_product', document.getElementById('productIsSubProduct').checked);
    formData.append('csrfmiddlewaretoken', getCSRFToken());
    
    fetch('/office/add-product/', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    
    
    .then(data => {
        if (data.success) {
            hideAddProductPopup();
            showMessage('Product added successfully', 'success');
            setTimeout(() => {
                window.location.href = window.location.pathname;
            }, 2000);
        } else {
            let errorMessage = 'Error adding product';
            if (data.errors) {
                const errors = Object.values(data.errors).flat();
                errorMessage += ': ' + errors.join(', ');
            }
            showMessage(errorMessage, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
    });
        
}

// CSRF token helper - read from meta tag
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

// Dashboard navigation
function goToDashboard() {
    window.location.href = "/office/dashboard/";
}

function showScoopSizesPopup() {
    // Get all product rows
    const productRows = document.querySelectorAll('.products-table tbody tr[data-product-id]');
    
    // Build the content
    let content = '<div style="display: flex; flex-direction: column; gap: 12px;">';
    
    productRows.forEach(row => {
        const productId = row.dataset.productId;
        const productName = row.querySelector('td:first-child').textContent.trim();
        const scoopSize = row.dataset.scoopSize || '';
        const displaySize = scoopSize ? scoopSize : '--';
        
        content += `
            <div id="scoop-row-${productId}" style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: rgba(102, 126, 234, 0.05); border-radius: 8px; border: 1px solid rgba(102, 126, 234, 0.1);">
                <span style="font-weight: 600; color: #333;">${productName}</span>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span id="scoop-display-${productId}" style="color: #667eea; font-weight: 500; font-size: 0.95rem;">${displaySize}</span>
                    <input type="text" id="scoop-input-${productId}" value="${scoopSize}" style="display: none; flex: 1; padding: 4px 8px; border: 2px solid #667eea; border-radius: 4px; text-align: center;">
                    <span class="edit-icon" onclick="editScoopSize(${productId})" id="edit-btn-${productId}" title="Edit Scoop Size" style="cursor: pointer; color: #667eea; opacity: 0.6;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </span>
                    <button onclick="saveScoopSize(${productId})" id="save-btn-${productId}" style="display: none; padding: 4px 12px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; font-size: 0.85rem;">Save</button>
                    <button onclick="cancelEditScoopSize(${productId}, '${scoopSize}')" id="cancel-btn-${productId}" style="display: none; padding: 4px 12px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; font-size: 0.85rem;">Cancel</button>
                </div>
            </div>
        `;
    });
    
    content += '</div>';
    
    // Set the content
    document.getElementById('scoopSizesContent').innerHTML = content;
    
    // Show the popup
    document.getElementById('scoopSizesPopup').classList.add('show');
}

function hideScoopSizesPopup() {
    document.getElementById('scoopSizesPopup').classList.remove('show');
}

function closeScoopOnOutsideClick(event) {
    // Only close if the click was directly on the overlay (not on the popup content)
    if (event.target.id === 'scoopSizesPopup') {
        hideScoopSizesPopup();
    }
}

function editScoopSize(productId) {
    // Hide display and edit button
    document.getElementById(`scoop-display-${productId}`).style.display = 'none';
    document.getElementById(`edit-btn-${productId}`).style.display = 'none';
    
    // Show input, save, and cancel buttons
    document.getElementById(`scoop-input-${productId}`).style.display = 'block';
    document.getElementById(`save-btn-${productId}`).style.display = 'block';
    document.getElementById(`cancel-btn-${productId}`).style.display = 'block';
    
    // Focus on input
    document.getElementById(`scoop-input-${productId}`).focus();
}

function cancelEditScoopSize(productId, originalValue) {
    // Reset input to original value
    document.getElementById(`scoop-input-${productId}`).value = originalValue;
    
    // Hide input, save, and cancel buttons
    document.getElementById(`scoop-input-${productId}`).style.display = 'none';
    document.getElementById(`save-btn-${productId}`).style.display = 'none';
    document.getElementById(`cancel-btn-${productId}`).style.display = 'none';
    
    // Show display and edit button
    document.getElementById(`scoop-display-${productId}`).style.display = 'block';
    document.getElementById(`edit-btn-${productId}`).style.display = 'block';
}

function saveScoopSize(productId) {
    const newScoopSize = document.getElementById(`scoop-input-${productId}`).value.trim();
    
    // Disable buttons during save
    const saveBtn = document.getElementById(`save-btn-${productId}`);
    const cancelBtn = document.getElementById(`cancel-btn-${productId}`);
    saveBtn.disabled = true;
    cancelBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    
    // Make API call
    fetch('/office/update-product-scoop-size/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            product_id: productId,
            scoop_size: newScoopSize
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update the display
            const displayValue = newScoopSize || '--';
            document.getElementById(`scoop-display-${productId}`).textContent = displayValue;
            
            // Update the data attribute in the main table
            const productRow = document.querySelector(`tr[data-product-id="${productId}"]`);
            if (productRow) {
                productRow.dataset.scoopSize = newScoopSize;
            }
            
            // Hide edit mode
            cancelEditScoopSize(productId, newScoopSize);
            
            // Show success message
            showMessage('Scoop size updated successfully', 'success');
        } else {
            showMessage('Error updating scoop size: ' + (data.error || 'Unknown error'), 'error');
            saveBtn.disabled = false;
            cancelBtn.disabled = false;
            saveBtn.textContent = 'Save';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
        saveBtn.disabled = false;
        cancelBtn.disabled = false;
        saveBtn.textContent = 'Save';
    });
}