// Growout Prep JavaScript

let allRows = [];
let hasUnsavedChanges = false;

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    allRows = Array.from(document.querySelectorAll('#tableBody tr'));
    
    // Set up filter event listeners
    document.getElementById('statusFilter').addEventListener('change', applyFilters);
    document.getElementById('categoryFilter').addEventListener('change', applyFilters);
    document.getElementById('cropFilter').addEventListener('change', applyFilters);
    document.getElementById('growerFilter').addEventListener('change', applyFilters);

    // Set up grower select change handlers
    document.querySelectorAll('.grower-select').forEach(select => {
        select.addEventListener('change', handleInputChange);
    });

    populateGrowerFilter();
});


// Populate grower filter with assigned growers from the table
function populateGrowerFilter() {
    const growerFilter = document.getElementById('growerFilter');
    const growerSelects = document.querySelectorAll('.grower-select');
    const assignedGrowers = new Set();
    
    // Collect all assigned growers
    growerSelects.forEach(select => {
        const selectedOption = select.options[select.selectedIndex];
        if (selectedOption.value) {
            assignedGrowers.add(selectedOption.value + '|' + selectedOption.text);
        }
    });
    
    // Sort and populate the filter
    const sortedGrowers = Array.from(assignedGrowers).sort();
    sortedGrowers.forEach(growerData => {
        const [code, text] = growerData.split('|');
        const option = document.createElement('option');
        option.value = code;
        option.textContent = text;
        growerFilter.appendChild(option);
    });
}

// function applyFilters() {
//     const statusFilter = document.getElementById('statusFilter').value;
//     const categoryFilter = document.getElementById('categoryFilter').value;
//     const cropFilter = document.getElementById('cropFilter').value;
    
//     const growerFilterValue = document.getElementById('growerFilter').value.toLowerCase();

//     let visibleCount = 0;
    
//     allRows.forEach(row => {
//         const rowStatus = row.dataset.status;
//         const rowCategory = row.dataset.category;
//         const rowCrop = row.dataset.crop;
        
//         let showRow = true;
        
//         if (statusFilter && rowStatus !== statusFilter) {
//             showRow = false;
//         }
        
//         if (categoryFilter && rowCategory !== categoryFilter) {
//             showRow = false;
//         }
        
//         if (cropFilter && rowCrop !== cropFilter) {
//             showRow = false;
//         }

//         if (growerFilterValue) {
//             const growerSelect = row.querySelector('.grower-select');
//             const selectedGrowerCode = growerSelect.value.toLowerCase();
//             if (selectedGrowerCode !== growerFilterValue) {
//                 showRow = false;
//             }
//         }
                
//         if (showRow) {
//             row.style.display = '';
//             visibleCount++;
//         } else {
//             row.style.display = 'none';
//         }
//     });
    
//     document.getElementById('varietyCount').textContent = `${visibleCount} varieties`;
// }


function applyFilters() {
    const statusFilter = document.getElementById('statusFilter').value;
    const categoryFilter = document.getElementById('categoryFilter').value;
    const cropFilter = document.getElementById('cropFilter').value;
    const growerFilterValue = document.getElementById('growerFilter').value.toLowerCase();
    
    let visibleCount = 0;
    
    allRows.forEach(row => {
        const rowStatus = row.dataset.status;
        const rowCategory = row.dataset.category;
        const rowCrop = row.dataset.crop;
        
        let showRow = true;
        
        if (statusFilter && rowStatus !== statusFilter) {
            showRow = false;
        }
        
        if (categoryFilter && rowCategory !== categoryFilter) {
            showRow = false;
        }
        
        if (cropFilter && rowCrop !== cropFilter) {
            showRow = false;
        }
        
        if (growerFilterValue) {
            const growerSelect = row.querySelector('.grower-select');
            const selectedGrowerCode = growerSelect.value.toLowerCase();
            
            if (growerFilterValue === '__unallocated__') {
                // Show only rows with no grower assigned
                if (selectedGrowerCode !== '') {
                    showRow = false;
                }
            } else {
                // Normal grower filtering
                if (selectedGrowerCode !== growerFilterValue) {
                    showRow = false;
                }
            }
        }
                
        if (showRow) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
    
    // Update the variety count
    document.getElementById('varietyCount').textContent = `${visibleCount} showing`;
}


function decreaseYear(button) {
    const varietyId = button.dataset.varietyId;
    const row = button.closest('tr');
    const input = row.querySelector('.year-input');
    const minYear = parseInt(input.dataset.minYear);
    let currentYear = parseInt(input.value);
    
    if (currentYear > minYear) {
        input.value = currentYear - 1;
        handleInputChange();
    }
}

function increaseYear(button) {
    const varietyId = button.dataset.varietyId;
    const row = button.closest('tr');
    const input = row.querySelector('.year-input');
    let currentYear = parseInt(input.value);
    
    input.value = currentYear + 1;
    handleInputChange();
}

function toggleCreateLot(button) {
    const isCreated = button.dataset.created === 'true';
    
    if (isCreated) {
        // Switch back to X
        button.textContent = '✗';
        button.dataset.created = 'false';
        button.classList.remove('created');
    } else {
        // Switch to checkmark
        button.textContent = '✓';
        button.dataset.created = 'true';
        button.classList.add('created');
    }
    
    handleInputChange();
}

function handleInputChange() {
    hasUnsavedChanges = true;
    const saveBtn = document.getElementById('saveChangesBtn');
    saveBtn.disabled = false;
    saveBtn.classList.add('active');
}

function saveChanges() {
    console.log('Save changes clicked - collecting data...');
    
    const saveBtn = document.getElementById('saveChangesBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Validating...';
    
    const records = [];
    const validationErrors = [];
    
    allRows.forEach(row => {
        const varietyId = row.dataset.varietyId;
        const varietyName = row.dataset.varietyName;
        const prepId = row.dataset.prepId || null;
        const isLocked = row.dataset.locked === 'true';
        
        const growerSelect = row.querySelector('.grower-select');
        const yearInput = row.querySelector('.year-input');
        const createLotBtn = row.querySelector('.create-lot-btn');
        const qtyInput = row.querySelector('.qty-input');
        const priceInput = row.querySelector('.price-input');
        
        const growerCode = growerSelect.value;
        const quantity = qtyInput.value.trim();
        const price = priceInput.value.trim();
        const year = parseInt(yearInput.value);
        const lotCreated = createLotBtn.dataset.created === 'true';
        
        // VALIDATION: Check if lot is being created without a grower
        if (lotCreated && !growerCode && !isLocked) {
            validationErrors.push(`${varietyName}: Cannot create lot without selecting a grower`);
            // Highlight the row with error
            row.style.backgroundColor = '#fee';
            setTimeout(() => {
                row.style.backgroundColor = '';
            }, 3000);
        }
        
        // For locked rows, only save qty and price
        if (isLocked) {
            if (quantity || price) {
                records.push({
                    variety_id: varietyId,
                    prep_id: prepId,
                    grower_code: growerCode,
                    year: year,
                    quantity: quantity,
                    price_per_lb: price,
                    lot_created: lotCreated,
                    is_locked: true
                });
            }
        } else {
            // For unlocked rows, save if there's actual data entered
            if (growerCode || quantity || price || lotCreated) {
                records.push({
                    variety_id: varietyId,
                    prep_id: prepId,
                    grower_code: growerCode || null,
                    year: year,
                    quantity: quantity,
                    price_per_lb: price,
                    lot_created: lotCreated,
                    is_locked: false
                });
            }
        }
    });
    
    // If there are validation errors, stop and show them
    if (validationErrors.length > 0) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Changes';
        
        // Show all validation errors
        validationErrors.forEach(error => {
            showToast(error, 'error');
        });
        
        return;
    }
    
    if (records.length === 0) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Changes';
        showToast('No changes to save', 'warning');
        return;
    }
    
    saveBtn.textContent = 'Saving...';
    console.log('Sending to backend:', records);
    
    // Make the AJAX call
    fetch('/office/growout-prep/save/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.appData.csrfToken
        },
        body: JSON.stringify({ records: records })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Save successful:', data);
            
            // Update prep_ids and lock rows that had lots created
            data.saved_records.forEach(saved => {
                const rows = document.querySelectorAll(`tr[data-variety-id="${saved.variety_id}"]`);
                rows.forEach(row => {
                    if (!row.dataset.prepId || row.dataset.prepId === '' || row.dataset.prepId === saved.prep_id.toString()) {
                        row.dataset.prepId = saved.prep_id;
                        
                        // If lot was created, lock the row (but not qty/price)
                        if (saved.lot_created && saved.created_lot_id && !row.classList.contains('locked-row')) {
                            row.dataset.locked = 'true';
                            row.classList.add('locked-row');
                            
                            // Disable grower/year/create-lot controls only
                            row.querySelector('.grower-select').disabled = true;
                            row.querySelector('.year-input').disabled = true;
                            row.querySelectorAll('.year-btn').forEach(btn => btn.disabled = true);
                            row.querySelector('.create-lot-btn').disabled = true;
                            
                            // Replace button with lock icon (only if not first row)
                            const varietyCellContent = row.querySelector('.variety-cell-content');
                            const removeBtn = varietyCellContent.querySelector('.remove-row-btn');
                            if (removeBtn) {
                                const lockIndicator = document.createElement('div');
                                lockIndicator.className = 'lock-indicator';
                                lockIndicator.textContent = '🔒';
                                lockIndicator.title = 'Lot created';
                                removeBtn.replaceWith(lockIndicator);
                            }
                        }
                        
                        // Update all elements in this row to have the prep_id
                        row.querySelectorAll('[data-prep-id]').forEach(el => {
                            el.dataset.prepId = saved.prep_id;
                        });
                    }
                });
            });
            
            // Show success message with lot creation details
            let message = `Successfully saved ${records.length} record${records.length > 1 ? 's' : ''}`;
            if (data.created_lots && data.created_lots.length > 0) {
                message += ` • Created ${data.created_lots.length} lot${data.created_lots.length > 1 ? 's' : ''}`;
            }
            
            // Show any errors
            if (data.errors && data.errors.length > 0) {
                console.error('Errors:', data.errors);
                data.errors.forEach(error => {
                    showToast(error, 'error');
                });
            }
            
            saveBtn.textContent = 'Saved!';
            saveBtn.style.backgroundColor = '#10b981';
            showToast(message, 'success');
            
            setTimeout(() => {
                saveBtn.textContent = 'Save Changes';
                saveBtn.style.backgroundColor = '';
                resetSaveButton();
            }, 2000);
        } else {
            console.error('Save failed:', data.error);
            showToast('Error saving: ' + data.error, 'error');
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Changes';
        }
    })
    .catch(error => {
        console.error('Network error:', error);
        showToast('Network error - please try again', 'error');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Changes';
    });
}



// Toast notification system
function showToast(message, type = 'info') {
    // Remove any existing toasts
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    
    // Add to page
    document.body.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}


function addVarietyRow(button) {
    const varietyId = button.dataset.varietyId;
    const currentRow = button.closest('tr');
    
    // Disable the button temporarily
    button.disabled = true;
    button.textContent = '⋯';
    
    // Make AJAX call to create a new prep record
    fetch('/office/growout-prep/add-row/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.appData.csrfToken
        },
        body: JSON.stringify({ variety_id: varietyId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Clone the current row
            const newRow = currentRow.cloneNode(true);
            
            // IMPORTANT: Remove locked state from new row
            newRow.dataset.locked = 'false';
            newRow.classList.remove('locked-row');
            
            // Update the new row's data attributes
            newRow.dataset.prepId = data.prep_id;
            
            // Replace the + button with a - button
            const varietyCellContent = newRow.querySelector('.variety-cell-content');
            const addBtn = varietyCellContent.querySelector('.add-row-btn');
            const lockIcon = varietyCellContent.querySelector('.lock-indicator');
            
            // Remove either the + button or lock icon
            if (addBtn) {
                const removeBtn = document.createElement('button');
                removeBtn.className = 'remove-row-btn';
                removeBtn.dataset.varietyId = varietyId;
                removeBtn.dataset.prepId = data.prep_id;
                removeBtn.title = 'Remove this row';
                removeBtn.textContent = '−';
                removeBtn.onclick = function() { removeVarietyRow(this); };
                
                addBtn.replaceWith(removeBtn);
            } else if (lockIcon) {
                // If there was a lock icon, replace it with - button
                const removeBtn = document.createElement('button');
                removeBtn.className = 'remove-row-btn';
                removeBtn.dataset.varietyId = varietyId;
                removeBtn.dataset.prepId = data.prep_id;
                removeBtn.title = 'Remove this row';
                removeBtn.textContent = '−';
                removeBtn.onclick = function() { removeVarietyRow(this); };
                
                lockIcon.replaceWith(removeBtn);
            }
            
            // Enable all controls in the new row (clear disabled states)
            const growerSelect = newRow.querySelector('.grower-select');
            growerSelect.value = '';
            growerSelect.disabled = false;
            growerSelect.dataset.prepId = data.prep_id;
            
            const yearInput = newRow.querySelector('.year-input');
            yearInput.value = data.year;
            yearInput.disabled = false;
            yearInput.dataset.prepId = data.prep_id;
            
            const yearBtns = newRow.querySelectorAll('.year-btn');
            yearBtns.forEach(btn => {
                btn.disabled = false;
                btn.dataset.prepId = data.prep_id;
            });
            
            const qtyInput = newRow.querySelector('.qty-input');
            qtyInput.value = '';
            qtyInput.dataset.prepId = data.prep_id;
            
            const priceInput = newRow.querySelector('.price-input');
            priceInput.value = '';
            priceInput.dataset.prepId = data.prep_id;
            
            const createLotBtn = newRow.querySelector('.create-lot-btn');
            createLotBtn.textContent = '✗';
            createLotBtn.dataset.created = 'false';
            createLotBtn.disabled = false;
            createLotBtn.classList.remove('created');
            createLotBtn.dataset.prepId = data.prep_id;
            
            // Insert the new row after the current row
            currentRow.parentNode.insertBefore(newRow, currentRow.nextSibling);
            
            // Update allRows array
            allRows = Array.from(document.querySelectorAll('#tableBody tr'));
            
            // Set up event listener for the new grower select
            const newGrowerSelect = newRow.querySelector('.grower-select');
            newGrowerSelect.addEventListener('change', handleInputChange);
            
            // Re-enable the button
            button.disabled = false;
            button.textContent = '+';
            
            // Update variety count
            applyFilters();
            
            showToast('New row added - assign grower and save changes', 'success');
        } else {
            button.disabled = false;
            button.textContent = '+';
            showToast('Error adding row: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        button.disabled = false;
        button.textContent = '+';
        showToast('Network error - please try again', 'error');
    });
}

// Modal state
let pendingDeleteButton = null;

function showConfirmModal(message, button) {
    const modal = document.getElementById('confirmModal');
    const messageEl = document.getElementById('confirmMessage');
    
    messageEl.textContent = message;
    pendingDeleteButton = button;
    
    modal.classList.add('show');
    document.body.classList.add('modal-open');
}

function closeConfirmModal() {
    const modal = document.getElementById('confirmModal');
    
    modal.classList.remove('show');
    document.body.classList.remove('modal-open');
    pendingDeleteButton = null;
}

function confirmDelete() {
    if (pendingDeleteButton) {
        // Actually execute the delete
        executeRemoveRow(pendingDeleteButton);
    }
    closeConfirmModal();
}

function removeVarietyRow(button) {
    const row = button.closest('tr');
    const varietyName = row.dataset.varietyName;
    const isLocked = row.dataset.locked === 'true';
    
    if (isLocked) {
        showToast('Cannot delete: Lot has been created for this row', 'error');
        return;
    }
    
    // Show custom confirmation modal
    showConfirmModal(
        `Are you sure you want to remove this growout row for ${varietyName}?`,
        button
    );
}

// Separate function to actually execute the removal
function executeRemoveRow(button) {
    const row = button.closest('tr');
    const prepId = button.dataset.prepId;
    
    // Disable the button temporarily
    button.disabled = true;
    button.textContent = '⋯';
    
    // If there's a prep_id, delete from database
    if (prepId && prepId !== '') {
        fetch('/office/growout-prep/delete-row/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.appData.csrfToken
            },
            body: JSON.stringify({ prep_id: prepId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove the row from DOM
                row.remove();
                
                // Update allRows array
                allRows = Array.from(document.querySelectorAll('#tableBody tr'));
                
                // Update variety count
                applyFilters();
                
                showToast('Row removed successfully', 'success');
            } else {
                button.disabled = false;
                button.textContent = '−';
                showToast('Error removing row: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            button.disabled = false;
            button.textContent = '−';
            showToast('Network error - please try again', 'error');
        });
    } else {
        // No prep_id, just remove from DOM (shouldn't happen but handle it)
        row.remove();
        allRows = Array.from(document.querySelectorAll('#tableBody tr'));
        applyFilters();
        showToast('Row removed', 'success');
    }
}

// Optional: Close modal when clicking outside
document.addEventListener('click', function(event) {
    const modal = document.getElementById('confirmModal');
    if (modal && event.target === modal) {
        closeConfirmModal();
    }
});

// Optional: Close modal with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeConfirmModal();
    }
});


function resetSaveButton() {
    hasUnsavedChanges = false;
    const saveBtn = document.getElementById('saveChangesBtn');
    saveBtn.disabled = true;
    saveBtn.classList.remove('active');
}

// CSRF token helper
function getCSRFToken() {
    return window.appData.csrfToken || '';
}