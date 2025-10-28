
// const varietyDataString = '{{ all_vars_json|escapejs }}';
// const packedForYear = '{{ packed_for_year }}'; // e.g., "26" or "25"
// const isTransition = JSON.parse('{{ transition|yesno:"true,false"|lower }}');
// const lotsExtraData = JSON.parse('{{ lots_extra_data|escapejs }}');
let allVarieties = JSON.parse(varietyDataString);
// const lotsDataString = '{{ lots_json|escapejs }}';
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
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

        // Only search through the common_spelling keys
        const matches = [];
        
        for (const [skuPrefix, data] of Object.entries(allVarieties)) {
            const matchesCommonSpelling = data.common_spelling && data.common_spelling.toLowerCase().includes(query);
            
            if (matchesCommonSpelling) {
                matches.push([skuPrefix, data]);
            }
        }
        // console.log('Found matches:', matches.length);

        if (matches.length > 0) {

            searchDropdown.innerHTML = matches.slice(0, 10).map(([skuPrefix, data]) => `
                <div class="dropdown-item" onclick="selectVariety('${skuPrefix}')">
                    <div class="dropdown-variety-name">${data.var_name || data.common_spelling}</div>
                    <div class="dropdown-variety-type">${data.veg_type || ''}</div>
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
                showMessage('Local Flask printing app not running', 'error');
                return;
            }
            
            // Flask is running, proceed with normal print popup logic
            console.log('Proceeding with print popup checks...');
            proceedWithPrintPopupChecks(productId, productName);
        })
        .catch(error => {
            console.error('Error checking Flask connection:', error);
            showMessage('Local Flask printing app not running', 'error');
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
        const matchingLot = allLotsData.find(lot => {
            const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
            return lotDisplay === lotText;
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
    const matchingLot = allLotsData.find(lot => {
        const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
        return lotDisplay === lotCode;
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
        veg_type: document.getElementById('editVegType').value,
        species: document.getElementById('editSpecies').value,
        supergroup: document.getElementById('editSupergroup').value,
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
            'X-CSRFToken': getCookie('csrftoken')
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



// function editProduct(productId) {
//     hideProductActionsPopup();
    
//     currentProductId = productId || currentProductId;
//     // Get product data from the row
//     const productRow = document.querySelector(`tr[data-product-id="${productId}"]`);
    
//     if (!productRow) {
//         showMessage('Could not find product data', 'error');
//         return;
//     }
    
//     // Pre-fill all the form fields
//     document.getElementById('editProductVariety').value = productRow.dataset.varietyName || '';
//     document.getElementById('editProductSkuSuffix').value = productRow.dataset.skuSuffix || '';
//     document.getElementById('editProductPkgSize').value = productRow.dataset.pkgSize || '';
//     document.getElementById('editProductAltSku').value = productRow.dataset.altSku || '';
//     document.getElementById('editProductLineitemName').value = productRow.dataset.lineitemName || '';
//     document.getElementById('editProductRackLocation').value = productRow.dataset.rackLocation || '';
//     document.getElementById('editProductEnvType').value = productRow.dataset.envType || '';
//     document.getElementById('editProductEnvMultiplier').value = productRow.dataset.envMultiplier || '1';
//     document.getElementById('editProductScoopSize').value = productRow.dataset.scoopSize || '';
    
//     // Handle checkboxes - convert string to boolean
//     document.getElementById('editProductPrintBack').checked = productRow.dataset.printBack === 'true';
//     document.getElementById('editProductIsSubProduct').checked = productRow.dataset.isSubProduct === 'true';
    
//     // Show the popup
//     document.getElementById('editProductPopup').classList.add('show');
//     document.body.classList.add('modal-open');
// }

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
    
    formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
    
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
            'X-CSRFToken': getCookie('csrftoken')
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
            'X-CSRFToken': getCookie('csrftoken')
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
            'X-CSRFToken': getCookie('csrftoken')
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


function submitPrintJob() {
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
        // Collect all data from the page
        const printData = collectPrintData(currentProductId, quantity);
        
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
                // Step 2: Record print job in Django after all printing is complete
                return fetch('/office/print-product-labels/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        product_id: currentProductId,
                        print_type: selectedPrintOption,
                        quantity: quantity,
                        packed_for_year: printData.for_year
                    })
                });
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage(`Successfully printed ${quantity} ${selectedPrintOption.replace('_', ' ')} label(s)`, 'success');
                    hidePrintPopup(); // This will reset the buttons when popup closes
                    // Refresh page after 2 seconds to show updated print count
                    setTimeout(() => {
                        window.location.href = window.location.pathname;
                    }, 2000);
                } else {
                    showMessage('Print sent but failed to record: ' + (data.error || 'Unknown error'), 'error');
                    hidePrintPopup(); // This will reset the buttons when popup closes
                }
            })
            .catch(error => {
                console.error('Print job error:', error);
                console.log('This is the data that would be sent to Flask:', printData);
                showMessage('Printing failed: ' + error.message, 'error');
                resetPrintButtons(printBtn, cancelBtn, popup, originalPrintText);
            });

    } catch (error) {
        console.error('Data collection error:', error);
        console.log('This is the data that would be sent to Flask: [Data collection failed]');
        showMessage('Failed to collect print data', 'error');
        resetPrintButtons(printBtn, cancelBtn, popup, originalPrintText);
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



function collectPrintData(productId, quantity) {
    const productRow = document.querySelector(`tr[data-product-id="${productId}"]`);
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
        for_year: selectedYear, // Use the selected year instead of fixed value
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
            'X-CSRFToken': getCookie('csrftoken')
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
            'X-CSRFToken': getCookie('csrftoken')
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
            'X-CSRFToken': getCookie('csrftoken')
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
            'X-CSRFToken': getCookie('csrftoken')
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
        button.textContent = `${lot.grower}${lot.year}${lot.harvest}`;
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
    
    fetch('/office/assign-lot-to-product/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            product_id: productId,
            lot_id: lotId,
            change_all_products: changeAllProducts
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show appropriate success message
            const message = changeAllProducts 
                ? `Lot updated for all products in this variety`
                : `Lot updated for selected product`;
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
            'X-CSRFToken': getCookie('csrftoken')
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
        // Get variety name from the page (assuming it's available)
        const varietyName = document.getElementById('varietyName').textContent.trim();
        const lotDisplay = `${lot.grower}${lot.year}${lot.harvest}`;
        title = `Retiring ${varietyName} ${lotDisplay}`;
    }
    
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('retireLotTitle').textContent = title;
    document.getElementById('retireLotPopup').classList.add('show');
}

function hideRetireLotPopup() {
    document.getElementById('retireLotPopup').classList.remove('show');
    document.getElementById('retireLotForm').reset();
}

function submitRetireLot(event) {
    event.preventDefault();
    
    const lbsRemaining = document.getElementById('retireLbsInput').value;
    const notes = document.getElementById('retireNotesInput').value;
    const retireDate = document.getElementById('retireDateInput').value;

    console.log('Form data:', { // ADD THIS
        lot_id: currentLotId,
        lbs_remaining: lbsRemaining,
        retire_date: retireDate,
        notes: notes
    });
    
    fetch('/office/retire-lot/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            lot_id: currentLotId,
            lbs_remaining: lbsRemaining,
            retire_date: retireDate,
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Response data:', data);
        if (data.success) {
            localStorage.removeItem('germination_inventory_data'); // Clear the cached data directly
            showMessage('Lot retired successfully', 'success');
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
                showMessage('Local Flask printing app not running', 'error');
                return;
            }
            
            console.log('About to send request to Django with lot_id:', lotId);
            
            // Fetch existing stock seed data from Django
            fetch('/office/get-stock-seed-data/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
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
                        veg_type: data.veg_type,
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
            showMessage('Local Flask printing app not running', 'error');
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
                showMessage('Local Flask printing app not running - cannot print stock seed label', 'error');
                return;
            }
            
            // Flask is running, proceed with Django backend submission
            console.log('Flask healthy, proceeding with stock seed recording...');
            proceedWithStockSeedSubmission(qty, notes);
        })
        .catch(error => {
            console.error('Error checking Flask connection for stock seed:', error);
            showMessage('Local Flask printing app not running - cannot print stock seed label', 'error');
        });
}

function proceedWithStockSeedSubmission(qty, notes) {
    // Submit to Django backend first
    fetch('/office/record-stock-seed/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
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
        const vegType = document.getElementById('varietyType').textContent.trim();
        
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
            veg_type: vegType,
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
            'X-CSRFToken': getCookie('csrftoken')
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
            'X-CSRFToken': getCookie('csrftoken')
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
            'X-CSRFToken': getCookie('csrftoken')
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
            'X-CSRFToken': getCookie('csrftoken')
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

function viewLotUsage(lotId) {
    hideLotActionsPopup();
    console.log('View usage for lot:', lotId);
    showMessage('View Usage functionality coming soon', 'success');
    // TODO: Implement usage view popup
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
                'X-CSRFToken': getCookie('csrftoken')
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
    formData.append('label', document.getElementById('productLabel').value);
    formData.append('num_printed', document.getElementById('productNumPrinted').value);
    formData.append('num_printed_next_year', document.getElementById('productNumPrintedNextYear').value);
    formData.append('scoop_size', document.getElementById('productScoopSize').value);
    formData.append('bulk_pre_pack', document.getElementById('productBulkPrePack').value);
    formData.append('print_back', document.getElementById('productPrintBack').checked);
    formData.append('is_sub_product', document.getElementById('productIsSubProduct').checked);
    formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
    
    fetch('/office/add-product/', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
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
    
    hideAddProductPopup();
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

// Dashboard navigation
function goToDashboard() {
    window.location.href = "/office/dashboard/";
}