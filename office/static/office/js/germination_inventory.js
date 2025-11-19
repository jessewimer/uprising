// Global state - simple and clean
let appData = {
    allLots: [],
    filteredLots: [],
    germYears: [],
    currentYear: null,
    germYear: null,
    categories: [],
    groups: [],
    vegTypes: []
};
let currentBulkJob = null; 
let currentPrintJob = null;

// CSRF helper
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing page...');
    loadData();
    setupEventListeners();
});

// Event listeners
function setupEventListeners() {
    document.getElementById('categoryFilter').addEventListener('change', applyFilters);
    document.getElementById('groupFilter').addEventListener('change', applyFilters);
    document.getElementById('vegTypeFilter').addEventListener('change', applyFilters);
    document.getElementById('websiteFilter').addEventListener('change', applyFilters);
    document.getElementById('clearFiltersBtn').addEventListener('click', clearFilters);
    document.getElementById('modalCancel').addEventListener('click', closeModal);
    document.getElementById('modalConfirm').addEventListener('click', confirmPrint);
    document.getElementById('salesModalClose').addEventListener('click', closeSalesModal);
    document.getElementById('bulkModalCancel').addEventListener('click', closeBulkModal);
    document.getElementById('bulkModalConfirm').addEventListener('click', confirmBulk);
    
    
    // Modal backdrop clicks
    document.getElementById('printModal').addEventListener('click', function(e) {
        if (e.target === this) closeModal();
    });
    document.getElementById('salesModal').addEventListener('click', function(e) {
        if (e.target === this) closeSalesModal();
    });
    document.getElementById('bulkModal').addEventListener('click', function(e) {
        if (e.target === this) closeBulkModal();
    });
    
    // Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeModal();
            closeSalesModal();
            closeBulkModal();
        }
    });
}

// Add wholesale checkbox change handler
// document.getElementById('wholesaleCheckbox')?.addEventListener('change', function() {
//     const rackTypeContainer = document.getElementById('rackTypeContainer');
//     if (this.checked) {
//         rackTypeContainer.style.display = 'block';
//     } else {
//         rackTypeContainer.style.display = 'none';
//         // Clear rack selection when unchecking wholesale
//         document.querySelectorAll('input[name="rackType"]').forEach(radio => {
//             radio.checked = false;
//         });
//     }
// });

// Add wholesale checkbox change handler
document.getElementById('wholesaleCheckbox')?.addEventListener('change', function() {
    const rackTypeContainer = document.getElementById('rackTypeContainer');
    if (this.checked) {
        rackTypeContainer.style.display = 'block';
    } else {
        rackTypeContainer.style.display = 'none';
        // DON'T clear the selection - just hide it
    }
});

// Cache configuration
const CACHE_KEY = 'germination_inventory_data';
const CACHE_DURATION = 10 * 60 * 1000; // 10 minutes in milliseconds

// Check if cached data is still valid
function isCacheValid() {
    const cached = localStorage.getItem(CACHE_KEY);
    if (!cached) return false;
    
    try {
        const data = JSON.parse(cached);
        const now = Date.now();
        return (now - data.timestamp) < CACHE_DURATION;
    } catch (e) {
        return false;
    }
}

// Get cached data
function getCachedData() {
    try {
        const cached = localStorage.getItem(CACHE_KEY);
        if (cached) {
            return JSON.parse(cached).data;
        }
    } catch (e) {
        console.error('Error reading cache:', e);
    }
    return null;
}

// Save data to cache
function setCachedData(data) {
    try {
        const cacheObject = {
            timestamp: Date.now(),
            data: data
        };
        localStorage.setItem(CACHE_KEY, JSON.stringify(cacheObject));
        console.log('Data cached successfully');
    } catch (e) {
        console.error('Error saving to cache:', e);
    }
}

// Clear cache (useful after data changes)
function clearCache() {
    localStorage.removeItem(CACHE_KEY);
    console.log('Cache cleared');
}

// Load data with caching
function loadData() {
    // Check cache first
    if (isCacheValid()) {
        const cachedData = getCachedData();
        if (cachedData) {
            console.log('Loading from cache...');
            processLoadedData(cachedData);
            return;
        }
    }
    
    // Cache miss or stale - fetch from server
    console.log('Cache miss - loading from server...');
    
    fetch(window.appUrls.germinationInventoryData)
        .then(response => response.json())
        .then(data => {
            console.log('Data loaded from server:', data);
            
            // Save to cache
            setCachedData(data);
            
            // Process data
            processLoadedData(data);
        })
        .catch(error => {
            console.error('Error loading data:', error);
            showError('Failed to load data. Please refresh the page.');
            hideLoading();
        });
}

// Process loaded data (whether from cache or server)
function processLoadedData(data) {
    appData.allLots = data.inventory_data;
    appData.germYears = data.germ_years;
    appData.currentYear = data.current_year;
    appData.germYear = data.germ_year;
    appData.categories = data.categories;
    appData.groups = data.groups;
    appData.vegTypes = data.veg_types;
    
    setupTable();
    populateFilters();
    appData.filteredLots = [...appData.allLots];
    renderTable();
    hideLoading();
}

// Setup table headers
function setupTable() {
    const headerRow = document.getElementById('tableHeader');
    
    // Add germination columns
    appData.germYears.forEach(year => {
        const th = document.createElement('th');
        th.textContent = `Germ ${year}`;
        headerRow.appendChild(th);
    });
}

// Populate filters
function populateFilters() {
    const categorySelect = document.getElementById('categoryFilter');
    const groupSelect = document.getElementById('groupFilter');
    const vegTypeSelect = document.getElementById('vegTypeFilter');

    categorySelect.innerHTML = '<option value="">All Categories</option>';
    groupSelect.innerHTML = '<option value="">All Groups</option>';
    vegTypeSelect.innerHTML = '<option value="">All Veg Types</option>';

    appData.categories.forEach(category => {
        if (category) {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            categorySelect.appendChild(option);
        }
    });

    appData.groups.forEach(group => {
        if (group) {
            const option = document.createElement('option');
            option.value = group;
            option.textContent = group;
            groupSelect.appendChild(option);
        }
    });

    appData.vegTypes.forEach(vegType => {
        if (vegType) {
            const option = document.createElement('option');
            option.value = vegType;
            option.textContent = vegType;
            vegTypeSelect.appendChild(option);
        }
    });
}

// Apply filters
function applyFilters() {
    const categoryFilter = document.getElementById('categoryFilter').value;
    const groupFilter = document.getElementById('groupFilter').value;
    const vegTypeFilter = document.getElementById('vegTypeFilter').value;
    const websiteFilter = document.getElementById('websiteFilter').value; // ADD THIS

    appData.filteredLots = appData.allLots.filter(lot => {
        // Website filter check - ADD THIS BLOCK
        let websiteMatch = true;
        if (websiteFilter !== '') {
            websiteMatch = lot.website_bulk === (websiteFilter === 'true');
        }
        
        return (!categoryFilter || lot.category === categoryFilter) &&
                (!groupFilter || lot.group === groupFilter) &&
                (!vegTypeFilter || lot.veg_type === vegTypeFilter) &&
                websiteMatch; // ADD THIS
    });

    renderTable();
}

// Clear filters
function clearFilters() {
    document.getElementById('categoryFilter').value = '';
    document.getElementById('groupFilter').value = '';
    document.getElementById('vegTypeFilter').value = '';
    document.getElementById('websiteFilter').value = '';
    appData.filteredLots = [...appData.allLots];
    renderTable();
}

// Get germination display
function getGerminationDisplay(lot, year) {
    const isCurrentYear = year === appData.currentYear;
    const germRate = lot.germination_rates[year];
    const labelPrinted = lot.germ_sample_prints && lot.germ_sample_prints[year];
    const germRecord = lot.germination_records && lot.germination_records[year];
    
    if (isCurrentYear) {
        if (germRecord && germRecord.germination_rate !== null && germRecord.germination_rate !== undefined) {
            if (germRecord.germination_rate === 0) {
                return { text: 'Germ Sent', className: 'germ-sent' };
            } else {
                let className = 'germ-cell';
                if (germRecord.germination_rate >= 85) className += ' germ-good';
                else if (germRecord.germination_rate >= 70) className += ' germ-fair';
                else className += ' germ-poor';
                return { text: `${germRecord.germination_rate}%`, className };
            }
        } else if (labelPrinted) {
            return { text: 'Label Printed', className: 'germ-label-printed' };
        } else {
            return { text: '-', className: 'germ-cell' };
        }
    } else {
        if (germRate !== null && germRate !== undefined) {
            let className = 'germ-cell';
            if (germRate >= 85) className += ' germ-good';
            else if (germRate >= 70) className += ' germ-fair';
            else className += ' germ-poor';
            return { text: `${germRate}%`, className };
        } else {
            return { text: '-', className: 'germ-cell' };
        }
    }
}

// Render table
function renderTable() {
    const tbody = document.getElementById('tableBody');
    const emptyState = document.getElementById('emptyState');
    
    tbody.innerHTML = '';
    
    if (appData.filteredLots.length === 0) {
        emptyState.style.display = 'block';
        return;
    }
    
    emptyState.style.display = 'none';
    
    appData.filteredLots.forEach(lot => {
        const row = document.createElement('tr');
        
        // Variety cell with print and bulk icons
        const varietyCell = document.createElement('td');
        varietyCell.className = 'variety-cell';
        
        const varietyCellContent = document.createElement('div');
        varietyCellContent.className = 'variety-cell-content';
        
        // Print icon
        const printIcon = document.createElement('div');
        printIcon.className = 'print-icon';
        printIcon.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6,9 6,2 18,2 18,9"></polyline>
                <path d="M6,18H4a2,2,0,0,1-2-2V11a2,2,0,0,1,2-2H20a2,2,0,0,1,2,2v5a2,2,0,0,1-2,2H18"></path>
                <polyline points="6,14 18,14 18,22 6,22 6,14"></polyline>
            </svg>
        `;
        printIcon.addEventListener('click', () => showPrintModal(lot));
        
        // NEW: Bulk icon
        const bulkIcon = document.createElement('div');
        bulkIcon.className = lot.website_bulk ? 'bulk-icon bulk-icon-active' : 'bulk-icon bulk-icon-inactive';
        bulkIcon.innerHTML = 'B';
        bulkIcon.addEventListener('click', () => showBulkModal(lot));
        
        // Variety link
        const varietyLink = document.createElement('a');
        varietyLink.className = 'variety-link';
        varietyLink.textContent = lot.variety_name;
        varietyLink.addEventListener('click', () => showSalesData(lot.sku_prefix, lot.variety_name));
        
        varietyCellContent.appendChild(printIcon);
        varietyCellContent.appendChild(bulkIcon);  // NEW: Add bulk icon
        varietyCellContent.appendChild(varietyLink);
        varietyCell.appendChild(varietyCellContent);
        row.appendChild(varietyCell);
        
        // Lot cell
        const lotCell = document.createElement('td');
        lotCell.className = 'lot-cell';
        lotCell.textContent = lot.lot_code;
        row.appendChild(lotCell);
        
        // Current Inventory cell
        const currentInvCell = document.createElement('td');
        currentInvCell.className = 'inventory-cell';
        if (lot.current_inventory_weight !== null) {
            currentInvCell.textContent = `${lot.current_inventory_weight.toFixed(2)} lbs`;
            if (lot.current_inventory_date) {
                currentInvCell.title = `As of ${lot.current_inventory_date}`;
            }
        } else {
            currentInvCell.textContent = '-';
        }
        row.appendChild(currentInvCell);
        
        // Previous Inventory cell
        const prevInvCell = document.createElement('td');
        prevInvCell.className = 'inventory-cell';
        if (lot.previous_inventory_weight !== null) {
            prevInvCell.textContent = `${lot.previous_inventory_weight.toFixed(2)} lbs`;
            if (lot.previous_inventory_date) {
                prevInvCell.title = `As of ${lot.previous_inventory_date}`;
            }
        } else {
            prevInvCell.textContent = '-';
        }
        row.appendChild(prevInvCell);
        
        // Difference cell
        const diffCell = document.createElement('td');
        if (lot.inventory_difference !== null) {
            const sign = lot.inventory_difference > 0 ? '+' : '';
            diffCell.textContent = `${sign}${lot.inventory_difference.toFixed(2)}`;
            
            if (lot.inventory_difference > 0) {
                diffCell.className = 'positive-diff';
            } else if (lot.inventory_difference < 0) {
                diffCell.className = 'negative-diff';
            } else {
                diffCell.className = 'neutral-diff';
            }
        } else {
            diffCell.textContent = '-';
            diffCell.className = 'neutral-diff';
        }
        row.appendChild(diffCell);
        
        // Germination cells
        appData.germYears.forEach(year => {
            const germCell = document.createElement('td');
            const display = getGerminationDisplay(lot, year);
            germCell.textContent = display.text;
            germCell.className = display.className;
            row.appendChild(germCell);
        });
        
        tbody.appendChild(row);
    });
}


function showMessage(text, type = 'error') {
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

function checkFlaskConnection() {
    return new Promise((resolve) => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);
        
        fetch('http://localhost:5000/health', {
            method: 'GET',
            signal: controller.signal
        })
        .then(response => {
            clearTimeout(timeoutId);
            if (response.ok) {
                resolve(true);
            } else {
                resolve(false);
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            resolve(false);
        });
    });
}


// Handle print click
function handlePrint(lot) {
    console.log('Print clicked for:', lot.variety_name, lot.lot_code);
    
    // First check if Flask app is running
    checkFlaskConnection()
        .then(isFlaskRunning => {
            if (!isFlaskRunning) {
                showMessage('Local Flask printing app not running', 'error');
                return;
            }
            
            // Flask is running, proceed with normal print logic
            proceedWithPrintChecks(lot);
        })
        .catch(error => {
            console.error('Error checking Flask connection:', error);
            showMessage('Local Flask printing app not running', 'error');
        });
}

function proceedWithPrintChecks(lot) {
    currentPrintJob = {
        lot_id: lot.lot_id,
        variety_name: lot.variety_name,
        sku_prefix: lot.sku_prefix,
        lot_code: lot.lot_code,
        species: lot.species
    };
    
    // Check if warning needed
    const rightmostYear = appData.germYears[appData.germYears.length - 1];
    const currentGermYearFormatted = String(appData.germYear).padStart(2, '0');
    
    if (rightmostYear !== currentGermYearFormatted) {
        // New year - no warning
        console.log('New germ year - direct print');
        showModal(false);
    } else {
        // Check existing label
        const display = getGerminationDisplay(lot, rightmostYear);
        const hasLabel = display.text !== '-';
        console.log('Existing check:', display.text, hasLabel);
        showModal(hasLabel);
    }
}

// Show modal
function showModal(isWarning) {
    console.log('Showing modal, warning:', isWarning);
    
    const modal = document.getElementById('printModal');
    const icon = document.getElementById('modalIcon');
    const title = document.getElementById('modalTitle');
    const text = document.getElementById('modalText');
    const variety = document.getElementById('modalVariety');
    const extra = document.getElementById('modalExtraText');
    const btn = document.getElementById('modalConfirm');
    
    variety.textContent = `${currentPrintJob.variety_name} (${currentPrintJob.lot_code})`;
    
    if (isWarning) {
        icon.className = 'modal-icon warning';
        icon.innerHTML = '!';
        title.textContent = 'Label Already Printed';
        text.textContent = 'A germination sample label has already been printed for:';
        extra.style.display = 'block';
        btn.textContent = 'Continue';
        btn.className = 'modal-btn warning';
    } else {
        icon.className = 'modal-icon';
        icon.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6,9 6,2 18,2 18,9"></polyline>
                <path d="M6,18H4a2,2,0,0,1-2-2V11a2,2,0,0,1,2-2H20a2,2,0,0,1,2,2v5a2,2,0,0,1-2,2H18"></path>
                <polyline points="6,14 18,14 18,22 6,22 6,14"></polyline>
            </svg>
        `;
        title.textContent = 'Print Germination Label';
        text.textContent = 'Are you sure you want to print a germination sample label for:';
        extra.style.display = 'none';
        btn.textContent = 'Print Label';
        btn.className = 'modal-btn primary';
    }
    
    modal.style.display = 'block';
    console.log('Modal should be visible');
}

// Confirm print
function confirmPrint() {
    console.log('Print confirmed');
    
    if (!currentPrintJob) {
        console.error('No print job');
        return;
    }
    
    // Close modal but don't clear currentPrintJob yet
    document.getElementById('printModal').style.display = 'none';
    
    // Execute print (this will clear currentPrintJob when done)
    executePrint();
}

// Close modal
function closeModal() {
    console.log('Closing modal');
    document.getElementById('printModal').style.display = 'none';
    currentPrintJob = null;
}

// Execute print
function executePrint() {
    console.log('Executing print for:', currentPrintJob);
    
    // Create Django record
    fetch(window.appUrls.createGermSamplePrint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            lot_id: currentPrintJob.lot_id,
            germ_year: appData.germYear
        })
    })
    .then(response => {
        console.log('Raw response status:', response.status);
        console.log('Raw response ok:', response.ok);
        return response.json();
    })
    .then(data => {
        console.log('Parsed Django response:', data);
        console.log('data.success value:', data.success);
        console.log('data.success type:', typeof data.success);
        
        if (data.success === true) {
            console.log('Success condition met - updating UI');
            
            // Save print job data before clearing it
            const printJobData = { ...currentPrintJob };
            
            // Update UI immediately
            updateUIAfterPrint();
            
            // Try Flask in background with saved data
            tryFlaskPrint(printJobData);
        } else {
            console.error('Success condition failed. Data:', data);
            alert('Error creating print record: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Django fetch error:', error);
        alert('Error creating print record: Network or parsing error');
    });
}

// Update UI after print
function updateUIAfterPrint() {
    console.log('Updating UI after print');
    
    // Clear cache since data has changed
    clearCache();
    
    const rightmostYear = appData.germYears[appData.germYears.length - 1];
    const currentGermYearFormatted = String(appData.germYear).padStart(2, '0');
    
    if (rightmostYear !== currentGermYearFormatted) {
        // New year - rebuild table
        console.log('New germ year - rebuilding table');
        
        // Update years
        appData.germYears.shift();
        appData.germYears.push(currentGermYearFormatted);
        appData.currentYear = currentGermYearFormatted;
        
        // Update data
        appData.allLots.forEach(lot => {
            const newRates = {};
            appData.germYears.forEach(year => {
                if (year === currentGermYearFormatted) {
                    newRates[year] = null;
                } else {
                    newRates[year] = lot.germination_rates[year] || null;
                }
            });
            lot.germination_rates = newRates;
            
            if (lot.lot_id === currentPrintJob.lot_id) {
                if (!lot.germ_sample_prints) lot.germ_sample_prints = {};
                lot.germ_sample_prints[currentGermYearFormatted] = true;
            }
        });
        
        // Rebuild headers
        const headerRow = document.getElementById('tableHeader');
        while (headerRow.children.length > 5) {
            headerRow.removeChild(headerRow.lastChild);
        }
        appData.germYears.forEach(year => {
            const th = document.createElement('th');
            th.textContent = `Germ ${year}`;
            headerRow.appendChild(th);
        });
        
        // Re-filter and render
        applyFilters();
    } else {
        // Same year - just update data and cell
        console.log('Same year - updating cell');
        
        const lot = appData.allLots.find(l => l.lot_id === currentPrintJob.lot_id);
        if (lot) {
            if (!lot.germ_sample_prints) lot.germ_sample_prints = {};
            lot.germ_sample_prints[currentGermYearFormatted] = true;
        }
        
        // Find and update specific cell
        const rows = document.querySelectorAll('#tableBody tr');
        appData.filteredLots.forEach((lot, index) => {
            if (lot.lot_id === currentPrintJob.lot_id) {
                const cells = rows[index].querySelectorAll('td');
                const rightmostCell = cells[cells.length - 1];
                rightmostCell.textContent = 'Label Printed';
                rightmostCell.className = 'germ-cell germ-label-printed';
            }
        });
    }
    
    currentPrintJob = null;
    console.log('UI updated');
}

// Try Flask print in background
function tryFlaskPrint(printJobData) {
    const flaskData = {
        variety_name: printJobData.variety_name,
        sku_prefix: printJobData.sku_prefix,
        species: printJobData.species,
        lot_code: printJobData.lot_code,
        germ_year: appData.germYear
    };
    
    console.log('Trying Flask with:', flaskData);
    
    fetch('http://localhost:5000/print-germ-label', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flaskData),
        signal: AbortSignal.timeout(5000)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Flask success:', data);
    })
    .catch(error => {
        console.log('Flask failed, but this is the data that was sent:', flaskData);
        console.error('Flask error:', error.message);
    });
}

// Sales functions
function showSalesData(sku_prefix, variety_name) {
    document.getElementById('salesModalTitle').textContent = `Sales Data - ${variety_name}`;
    document.getElementById('salesModal').style.display = 'flex';
    
    // Clear all rack selections from previous modal opens
    document.querySelectorAll('input[name="rackType"]').forEach(radio => {
        radio.checked = false;
    });

    // Reset sales section
    document.getElementById('salesLoading').style.display = 'block';
    document.getElementById('salesTable').style.display = 'none';
    document.getElementById('salesEmpty').style.display = 'none';
    
    // ADD THIS: Reset usage section
    document.getElementById('usageSection').style.display = 'none';
    document.getElementById('usageLoading').style.display = 'block';
    document.getElementById('usageContent').style.display = 'none';
    document.getElementById('usageEmpty').style.display = 'none';
    
    fetch(window.appUrls.varietySalesData.replace('PLACEHOLDER', sku_prefix))
        .then(response => response.json())
        .then(data => {
            document.getElementById('salesLoading').style.display = 'none';
            
            if (data.sales_data && data.sales_data.length > 0) {
                populateSalesTable(data.sales_data, data.display_year);
                document.getElementById('salesTable').style.display = 'table';
            } else {
                document.getElementById('salesEmpty').style.display = 'block';
            }

            // Show wholesale section
            const wholesaleSection = document.getElementById('wholesaleSection');
            const wholesaleCheckbox = document.getElementById('wholesaleCheckbox');
            wholesaleSection.style.display = 'block';
            wholesaleCheckbox.checked = data.wholesale || false;
            wholesaleCheckbox.dataset.skuPrefix = data.sku_prefix;
            wholesaleCheckbox.dataset.originalValue = data.wholesale || false;
            wholesaleCheckbox.dataset.rackDesignation = data.wholesale_rack_designation || '';

            // Show/hide and set rack type based on wholesale status
            const rackTypeContainer = document.getElementById('rackTypeContainer');
            if (data.wholesale) {
                rackTypeContainer.style.display = 'block';
                if (data.wholesale_rack_designation) {
                    const rackValue = String(data.wholesale_rack_designation).trim();
                    const rackRadio = document.querySelector(`input[name="rackType"][value="${rackValue}"]`);
                    if (rackRadio) {
                        rackRadio.checked = true;
                    }
                }
            } else {
                rackTypeContainer.style.display = 'none';
                document.querySelectorAll('input[name="rackType"]').forEach(radio => {
                    radio.checked = false;
                });
            }
            
            // Show usage section
            const usageSection = document.getElementById('usageSection');
            usageSection.style.display = 'block';
            
            if (data.usage_data && data.usage_data.total_lbs > 0) {
                populateUsageData(data.usage_data);
            } else {
                document.getElementById('usageLoading').style.display = 'none';
                document.getElementById('usageEmpty').style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Sales error:', error);
            document.getElementById('salesLoading').style.display = 'none';
            document.getElementById('salesEmpty').style.display = 'block';
        });
}
// function showSalesData(sku_prefix, variety_name) {
//     document.getElementById('salesModalTitle').textContent = `Sales Data - ${variety_name}`;
//     document.getElementById('salesModal').style.display = 'flex';
    
//     // Clear all rack selections from previous modal opens
//     document.querySelectorAll('input[name="rackType"]').forEach(radio => {
//         radio.checked = false;
//     });

//     document.getElementById('salesLoading').style.display = 'block';
//     document.getElementById('salesTable').style.display = 'none';
//     document.getElementById('salesEmpty').style.display = 'none';
    
//     fetch(window.appUrls.varietySalesData.replace('PLACEHOLDER', sku_prefix))
//         .then(response => response.json())
//         .then(data => {
//             document.getElementById('salesLoading').style.display = 'none';
            
//             if (data.sales_data && data.sales_data.length > 0) {
//                 populateSalesTable(data.sales_data, data.display_year);
//                 document.getElementById('salesTable').style.display = 'table';
//             } else {
//                 document.getElementById('salesEmpty').style.display = 'block';
//             }

//             // Show usage section
//             const usageSection = document.getElementById('usageSection');
//             usageSection.style.display = 'block';
            
//             if (data.usage_data && data.usage_data.total_lbs > 0) {
//                 populateUsageData(data.usage_data);
//             } else {
//                 document.getElementById('usageLoading').style.display = 'none';
//                 document.getElementById('usageEmpty').style.display = 'block';
//             }
//             // ADD AFTER line 730 (after the if/else for sales data display)
//             // Show wholesale section
//             // const wholesaleSection = document.getElementById('wholesaleSection');
//             // const wholesaleCheckbox = document.getElementById('wholesaleCheckbox');
//             // wholesaleSection.style.display = 'block';
//             // wholesaleCheckbox.checked = data.wholesale || false;
//             // wholesaleCheckbox.dataset.skuPrefix = data.sku_prefix;
//             // wholesaleCheckbox.dataset.originalValue = data.wholesale || false;
//             // Show wholesale section
//             const wholesaleSection = document.getElementById('wholesaleSection');
//             const wholesaleCheckbox = document.getElementById('wholesaleCheckbox');
//             wholesaleSection.style.display = 'block';
//             wholesaleCheckbox.checked = data.wholesale || false;
//             wholesaleCheckbox.dataset.skuPrefix = data.sku_prefix;
//             wholesaleCheckbox.dataset.originalValue = data.wholesale || false;

//             wholesaleCheckbox.dataset.rackDesignation = data.wholesale_rack_designation || '';

//             // NEW: Show/hide and set rack type based on wholesale status
//             const rackTypeContainer = document.getElementById('rackTypeContainer');
//             if (data.wholesale) {
//                 rackTypeContainer.style.display = 'block';
//                 // Set the current rack designation
//                 console.log('Wholesale is true, rack designation from DB:', data.wholesale_rack_designation); // DEBUG
//                 if (data.wholesale_rack_designation) {
//                     const rackValue = String(data.wholesale_rack_designation).trim(); // Convert to string and trim
//                     console.log('Looking for rack with value:', rackValue); // DEBUG
//                     const rackRadio = document.querySelector(`input[name="rackType"][value="${rackValue}"]`);
//                     console.log('Found radio element:', rackRadio); // DEBUG
//                     if (rackRadio) {
//                         rackRadio.checked = true;
//                         console.log('Set radio to checked'); // DEBUG
//                     } else {
//                         console.log('Radio element not found!'); // DEBUG
//                     }
//                 }
//             } else {
//                 rackTypeContainer.style.display = 'none';
//                 // Clear all rack selections
//                 document.querySelectorAll('input[name="rackType"]').forEach(radio => {
//                     radio.checked = false;
//                 });
//             }
            
//         })
//         .catch(error => {
//             console.error('Sales error:', error);
//             document.getElementById('salesLoading').style.display = 'none';
//             document.getElementById('salesEmpty').style.display = 'block';
//         });
// }

function populateSalesTable(salesData, displayYear) {
    const tbody = document.getElementById('salesTableBody');
    const quantityHeader = document.getElementById('quantityHeader');
    tbody.innerHTML = '';
    
    quantityHeader.textContent = `Quantity Sold (${displayYear})`;
    
    salesData.forEach(item => {
        const row = document.createElement('tr');
        
        if (item.is_total) {
            row.className = 'sales-total-row';
        }
        
        const skuCell = document.createElement('td');
        skuCell.textContent = item.display_name;
        
        if (item.is_total) {
            skuCell.className = 'sales-total-text';
        } else if (item.is_packet) {
            skuCell.className = 'sales-packet-text';
        } else {
            skuCell.className = 'sales-bulk-text';
        }
        
        row.appendChild(skuCell);
        
        const qtyCell = document.createElement('td');
        qtyCell.textContent = item.quantity;
        
        if (item.is_total) {
            qtyCell.className = 'sales-total-text';
        } else if (item.is_packet) {
            qtyCell.className = 'sales-packet-text';
        } else {
            qtyCell.className = 'sales-bulk-text';
        }
        
        row.appendChild(qtyCell);
        tbody.appendChild(row);
    });
}


function populateUsageData(usageData) {
    document.getElementById('usageLoading').style.display = 'none';
    document.getElementById('usageContent').style.display = 'block';
    
    // Populate summary stats
    document.getElementById('usageSeasonRange').textContent = usageData.season_range;
    document.getElementById('usageTotalLbs').textContent = `${usageData.total_lbs.toFixed(2)} lbs`;
    document.getElementById('usageLotCount').textContent = usageData.lot_count;
    
    // Populate lot details table
    const tbody = document.getElementById('usageLotTableBody');
    tbody.innerHTML = '';
    
    usageData.lots.forEach(lot => {
        const row = document.createElement('tr');
        if (lot.retired) {
            row.className = 'usage-retired-row';
        }
        
        row.innerHTML = `
            <td>${lot.lot_code}${lot.retired ? ' (retired)' : ''}</td>
            <td>${lot.start_weight.toFixed(2)}</td>
            <td>${lot.end_weight.toFixed(2)}</td>
            <td class="usage-amount">${lot.usage.toFixed(2)}</td>
        `;
        
        tbody.appendChild(row);
    });
}


function closeSalesModal() {
    document.getElementById('salesModal').style.display = 'none';
}


// Show message notification
function showMessage(text, type = 'success') {
    const container = document.getElementById('messagesContainer');
    const message = document.createElement('div');
    message.className = `message message-${type}`;
    message.innerHTML = `
        <span class="message-text">${text}</span>
        <button class="message-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(message);
    
    // Auto-remove after 4 seconds
    setTimeout(() => {
        message.style.animation = 'slideOutRight 0.3s ease-out forwards';
        setTimeout(() => message.remove(), 300);
    }, 3000);
}

// Utils
function hideLoading() {
    document.getElementById('loadingState').style.display = 'none';
}

function showError(message) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="100%" style="text-align: center; color: #dc3545; padding: 40px;">
                ${message}
            </td>
        </tr>
    `;
}

// NEW: Show bulk modal
function showBulkModal(lot) {
    currentBulkJob = {
        sku_prefix: lot.sku_prefix,
        variety_name: lot.variety_name,
        current_status: lot.website_bulk  // NEW: Track current status
    };
    
    const modalTitle = document.querySelector('#bulkModal .modal-title');
    const modalMessage = document.querySelector('#bulkModal .modal-message > div:first-child');
    const confirmBtn = document.getElementById('bulkModalConfirm');
    
    if (lot.website_bulk) {
        // Currently green - offer to remove
        modalTitle.textContent = 'Remove Bulk Stock from Website';
        modalMessage.textContent = 'Are you sure you want to mark bulk stock as NOT available on the website for:';
        confirmBtn.textContent = 'Remove';
    } else {
        // Currently red - offer to add
        modalTitle.textContent = 'Confirm Bulk Stock on Website';
        modalMessage.textContent = 'Are you sure you want to mark bulk stock as available on the website for:';
        confirmBtn.textContent = 'Confirm';
    }
    
    document.getElementById('bulkModalVariety').textContent = lot.variety_name;
    document.getElementById('bulkModal').style.display = 'block';
}

// NEW: Close bulk modal
function closeBulkModal() {
    document.getElementById('bulkModal').style.display = 'none';
    currentBulkJob = null;
}

// NEW: Confirm bulk update
function confirmBulk() {
    if (!currentBulkJob) return;
    
    const skuPrefix = currentBulkJob.sku_prefix;
    const newStatus = !currentBulkJob.current_status;  // Toggle the status
    console.log('Updating bulk status to:', newStatus, 'for:', skuPrefix);
    
    closeBulkModal();
    
    // Update all lots with this sku_prefix in the data
    appData.allLots.forEach(lot => {
        if (lot.sku_prefix === skuPrefix) {
            lot.website_bulk = newStatus;
        }
    });
    
    appData.filteredLots.forEach(lot => {
        if (lot.sku_prefix === skuPrefix) {
            lot.website_bulk = newStatus;
        }
    });
    
    // Re-render the table
    renderTable();
    console.log('UI updated - B should be', newStatus ? 'green' : 'red', 'now');
    
    // Clear cache since data changed
    clearCache();
    
    // Post to backend
    fetch(window.appUrls.updateWebsiteBulk, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            sku_prefix: skuPrefix,
            website_bulk: newStatus  // Send the new status
        })
    })
    .then(response => {
        console.log('Response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Bulk update response:', data);
        
        if (!data.success) {
            alert('Error updating bulk status: ' + (data.error || 'Unknown error'));
            // Revert the change
            appData.allLots.forEach(lot => {
                if (lot.sku_prefix === skuPrefix) {
                    lot.website_bulk = !newStatus;
                }
            });
            appData.filteredLots.forEach(lot => {
                if (lot.sku_prefix === skuPrefix) {
                    lot.website_bulk = !newStatus;
                }
            });
            renderTable();
        } else {
            console.log('Backend update successful!');
        }
    })
    .catch(error => {
        console.error('Bulk update error:', error);
        alert('Error updating bulk status: Network error');
        // Revert the change
        appData.allLots.forEach(lot => {
            if (lot.sku_prefix === skuPrefix) {
                lot.website_bulk = !newStatus;
            }
        });
        appData.filteredLots.forEach(lot => {
            if (lot.sku_prefix === skuPrefix) {
                lot.website_bulk = !newStatus;
            }
        });
        renderTable();
    });
}

// Wholesale save handler
document.getElementById('wholesaleSaveBtn')?.addEventListener('click', function() {
    const checkbox = document.getElementById('wholesaleCheckbox');
    const skuPrefix = checkbox.dataset.skuPrefix;
    const newValue = checkbox.checked;
    const originalValue = checkbox.dataset.originalValue === 'true';
    
    // Get rack type selection
    const selectedRack = document.querySelector('input[name="rackType"]:checked');
    const rackDesignation = selectedRack ? selectedRack.value : null;
    const originalRack = checkbox.dataset.rackDesignation || null;
    
    // Validation: if wholesale is checked, rack type must be selected
    if (newValue && !rackDesignation) {
        showMessage('Please select a rack type before saving', 'error');
        return;
    }
    
    // Check if anything changed
    if (newValue === originalValue && rackDesignation === originalRack) {
        showMessage('No changes to save', 'error');
        return;
    }
    
    fetch('/office/update-variety-wholesale/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            sku_prefix: skuPrefix,
            wholesale: newValue,
            wholesale_rack_designation: newValue ? rackDesignation : null
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            checkbox.dataset.originalValue = newValue;
            checkbox.dataset.rackDesignation = newValue ? rackDesignation : '';
            showMessage('Wholesale status updated successfully', 'success');
        } else {
            showMessage('Error: ' + (data.error || 'Unknown error'), 'error');
            checkbox.checked = originalValue;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Network error occurred', 'error');
        checkbox.checked = originalValue;
    });
});
// // Wholesale save handler
// document.getElementById('wholesaleSaveBtn')?.addEventListener('click', function() {
//     const checkbox = document.getElementById('wholesaleCheckbox');
//     const skuPrefix = checkbox.dataset.skuPrefix;
//     const newValue = checkbox.checked;
//     const originalValue = checkbox.dataset.originalValue === 'true';
    
//     if (newValue === originalValue) {
//         showMessage('No changes to save', 'error'); // CHANGED
//         return;
//     }
    
//     fetch('/office/update-variety-wholesale/', {
//         method: 'POST',
//         headers: {
//             'Content-Type': 'application/json',
//             'X-CSRFToken': getCSRFToken()
//         },
//         body: JSON.stringify({
//             sku_prefix: skuPrefix,
//             wholesale: newValue
//         })
//     })
//     .then(response => response.json())
//     .then(data => {
//         if (data.success) {
//             checkbox.dataset.originalValue = newValue;
//             showMessage('Wholesale status updated successfully', 'success'); // CHANGED
//         } else {
//             showMessage('Error: ' + (data.error || 'Unknown error'), 'error'); // CHANGED
//             checkbox.checked = originalValue;
//         }
//     })
//     .catch(error => {
//         console.error('Error:', error);
//         showMessage('Network error occurred', 'error'); // CHANGED
//         checkbox.checked = originalValue;
//     });
// });