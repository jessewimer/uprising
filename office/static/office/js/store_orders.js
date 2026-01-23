// Django template data
const varietyData = window.varietyData;

// Global variables
let currentStore = '';
let currentOrderId = null;
let currentOrderData = null; // Store current order data including fulfilled_date
let orderItems = {};
let selectedVariety = null;
let currentLookupType = 'variety';
let hasUnsavedChanges = false;
let currentEditItem = null;
let currentShippingCost = 0;
let selectedOrdersForCombine = new Set();
// Flask configuration
const FLASK_BASE_URL = 'http://127.0.0.1:5000';

// CSRF token helper - read from meta tag
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

// Function to check Flask health
async function checkFlaskHealth() {
    try {
        const response = await fetch(`${FLASK_BASE_URL}/health`, {
            method: 'GET',
            signal: AbortSignal.timeout(3000) // 3 second timeout
        });
        
        if (!response.ok) {
            throw new Error('Flask health check failed');
        }
        
        const data = await response.json();
        return data.status === 'ok';
    } catch (error) {
        console.error('Flask health check error:', error);
        return false;
    }
}


// Function to mark changes as unsaved
function markUnsavedChanges() {
    hasUnsavedChanges = true;
    updateUnsavedIndicator();
    updateSaveButton();
}

// Function to mark changes as saved
function markChangesSaved() {
    hasUnsavedChanges = false;
    updateUnsavedIndicator();
    updateSaveButton();
}

// Function to update unsaved changes indicator
function updateUnsavedIndicator() {
    const indicator = document.getElementById('unsaved-indicator');
    indicator.style.display = hasUnsavedChanges ? 'block' : 'none';
}

// Function to open edit item modal
function openEditItemModal(key, varName) {
    currentEditItem = key;
    const item = orderItems[key];
    
    document.getElementById('edit-item-name').textContent = varName;
    document.getElementById('edit-item-photo').checked = item.hasPhoto;
    document.getElementById('edit-item-modal').style.display = 'block';
}

// Function to close edit item modal
function closeEditItemModal() {
    document.getElementById('edit-item-modal').style.display = 'none';
    currentEditItem = null;
}

// Function to save item edits
async function saveItemEdits() {
    if (!currentEditItem) return;
    
    const hasPhoto = document.getElementById('edit-item-photo').checked;
    const itemName = orderItems[currentEditItem].var_name;
    orderItems[currentEditItem].hasPhoto = hasPhoto;
    
    renderOrderTable();
    closeEditItemModal();
    
    // Auto-save when editing items from modal
    if (currentOrderId) {
        await saveOrderChanges();
        showNotification('Item Updated!', `${itemName} photo setting updated and saved automatically`);
    } else {
        showNotification('Item Updated!', `${itemName} photo setting has been updated`);
    }
}

// Function to remove item from edit modal
async function removeItemFromEdit() {
    if (!currentEditItem) return;
    
    const itemName = orderItems[currentEditItem].var_name;
    delete orderItems[currentEditItem];
    
    renderOrderTable();
    updateOrderStats();
    updateSaveButton();
    closeEditItemModal();
    
    // Auto-save when removing items from modal
    if (currentOrderId) {
        await saveOrderChanges();
        showNotification('Item Removed!', `${itemName} has been removed and saved automatically`);
    } else {
        showNotification('Item Removed!', `${itemName} has been removed from order`);
    }
}
function clearSearchInput() {
    document.getElementById('variety-search').value = '';
    document.getElementById('lookup-results').innerHTML = `
        <div class="no-results"><p>Start typing to search</p></div>
    `;
}

// Function to clear search input
function clearSearchInput() {
    document.getElementById('variety-search').value = '';
    document.getElementById('lookup-results').innerHTML = `
        <div class="no-results"><p>Start typing to search</p></div>
    `;
}

// Function to clear order builder
function clearOrderBuilder() {
    console.log('Clearing order builder');
    orderItems = {};
    currentOrderId = null;
    currentOrderData = null; // Clear order data
    hasUnsavedChanges = false;
    renderOrderTable();
    updateOrderStats();
    updateSaveButton();
    updateUnsavedIndicator();
}

// Function to update order statistics
function updateOrderStats() {
    const uniqueItems = Object.keys(orderItems).length;
    const totalPackets = Object.values(orderItems).reduce((sum, item) => sum + item.quantity, 0);
    document.getElementById('unique-items-count').textContent = uniqueItems;
    document.getElementById('total-packets-count').textContent = totalPackets;
}

// Function to update save button state
function updateSaveButton() {
    const saveBtn = document.getElementById('save-order-btn');
    // More robust check for finalized status - check if fulfilled_date exists and is not null/empty
    const isFinalized = currentOrderData && 
                        currentOrderData.fulfilled_date && 
                        currentOrderData.fulfilled_date !== null && 
                        currentOrderData.fulfilled_date.trim() !== '';
    
    if (isFinalized) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Order Finalized';
        saveBtn.style.opacity = '0.5';
    } else {
        // Normal logic for non-finalized orders
        saveBtn.disabled = !currentOrderId || Object.keys(orderItems).length === 0;
        saveBtn.textContent = 'Save Changes';
        saveBtn.style.opacity = '1';
    }
}

function sortOrderItems(items) {
    const categoryOrder = { 'Vegetables': 1, 'Flowers': 2, 'Herbs': 3 };
    
    // Debug: Log what categories we're actually seeing
    console.log('Categories found in items:', Object.values(items).map(item => item.category));
    
    return Object.entries(items).sort(([keyA, itemA], [keyB, itemB]) => {
        // First sort by category
        const catA = categoryOrder[itemA.category] || 999;
        const catB = categoryOrder[itemB.category] || 999;
        
        console.log(`Comparing: ${itemA.var_name} (${itemA.category} = ${catA}) vs ${itemB.var_name} (${itemB.category} = ${catB})`);
        
        if (catA !== catB) return catA - catB;
        
        // Then sort by sku_prefix (since items are keyed by sku_prefix)
        return keyA.localeCompare(keyB);
    });
}

// Function to open bulk photo modal
function openBulkPhotoModal() {
    const isFinalized = currentOrderData && 
                    currentOrderData.fulfilled_date && 
                    currentOrderData.fulfilled_date !== null && 
                    currentOrderData.fulfilled_date.trim() !== '';
    
    if (isFinalized) {
        showNotification('Order Finalized', 
            'Cannot modify photos on a finalized order', 
            'error', '🔒');
        return;
    }

    if (Object.keys(orderItems).length === 0) {
        showNotification('Empty Order', 
            'Add items to the order first', 
            'warning', '⚠️');
        return;
    }

    document.getElementById('bulk-photo-modal').style.display = 'block';
}

// Function to close bulk photo modal
function closeBulkPhotoModal() {
    document.getElementById('bulk-photo-modal').style.display = 'none';
}

// Function to include all photos
async function includeAllPhotos() {
    Object.keys(orderItems).forEach(key => {
        orderItems[key].hasPhoto = true;
    });

    markUnsavedChanges();
    renderOrderTable();
    updateSaveButton();
    closeBulkPhotoModal();

    // Auto-save the changes
    await saveOrderToDatabase();
    showNotification('Photos Included', 
        'All items now include photos', 
        'success', '✅');
}

// Function to remove all photos
async function removeAllPhotos() {
    Object.keys(orderItems).forEach(key => {
        orderItems[key].hasPhoto = false;
    });

    markUnsavedChanges();
    renderOrderTable();
    updateSaveButton();
    closeBulkPhotoModal();

    // Auto-save the changes
    await saveOrderToDatabase();
    showNotification('Photos Removed', 
        'All photo selections have been removed', 
        'success', '✅');
}




async function setPhotosAutomatically() {
    if (!currentOrderId) {
        alert('Error: No order is currently loaded');
        return;
    }
    
    try {
        const response = await fetch('/office/set-photos-auto/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                order_id: currentOrderId
            })
        });

        const data = await response.json();

        if (data.success) {
            // Update the orderItems with new photo settings using sku_prefix
            data.photo_settings.forEach(setting => {
                if (orderItems[setting.sku_prefix]) {
                    orderItems[setting.sku_prefix].hasPhoto = setting.has_photo;
                }
            });
            
            markUnsavedChanges();
            renderOrderTable();
            updateSaveButton();
            closeBulkPhotoModal();
            
            showNotification('Photos Set Automatically', 
                'Photos have been set based on order history', 
                'success', '✅');
        } else {
            showNotification('Error', 
                data.error || 'Failed to set photos automatically', 
                'error', '❌');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Error', 
            'An error occurred while setting photos automatically', 
            'error', '❌');
    }
}


// Function to render order table
function renderOrderTable(readOnly = false) {
    const container = document.getElementById('order-table-container');
    if (Object.keys(orderItems).length === 0) {
        container.innerHTML = `
            <div class="empty-order">
                <div class="empty-order-icon">📦</div>
                <p>No items in order</p>
                <small>Search and add varieties from the right panel</small>
            </div>
        `;
        return;
    }

    // Sort the items before rendering
    const sortedItems = sortOrderItems(orderItems);
    
    const tableHTML = `
        <table class="order-table">
            <thead>
                <tr>
                    <th style="width: 80px;">Qty</th>
                    <th>Variety</th>
                    <th>Crop Type</th>
                    <th style="width: 60px;" id="photo-header" ${!readOnly && Object.keys(orderItems).length > 0 ? 'class="clickable-header" onclick="openBulkPhotoModal()" title="Click to bulk edit photos"' : ''}>Photo</th>
                </tr>
            </thead>
            <tbody>
                ${sortedItems.map(([key, item]) => `
                    <tr class="${item.quantity === 0 ? 'backordered-item' : ''}" ${readOnly ? 'style="cursor: default; opacity: 0.8;"' : `onclick="openEditItemModal('${key}', '${item.var_name.replace(/'/g, "\\'")}')" style="cursor: pointer;"`}>
                        <td>
                            ${readOnly ? 
                                `<span style="padding: 5px; display: inline-block; width: 60px; text-align: center; background: #f8f9fa; border-radius: 4px;">${item.quantity}</span>` :
                                `<input type="number" value="${item.quantity}" min="0" 
                                    style="width: 60px; padding: 5px; border: 1px solid #ddd; border-radius: 4px;"
                                    onchange="updateQuantity('${key}', this.value)" onclick="event.stopPropagation();">`
                            }
                        </td>
                        <td style="font-weight: 600;">${item.var_name}</td>
                        <td><span class="variety-crop">${item.crop}</span></td>
                        <td><span style="font-size: 1.2rem; color: ${item.hasPhoto ? '#26de81' : '#ff6b6b'};">${item.hasPhoto ? '✓' : '✗'}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    container.innerHTML = tableHTML;
}


function updateQuantity(key, newQuantity) {
    const qty = parseInt(newQuantity);
    if (qty >= 0) {  // ← Allow 0 or greater
        orderItems[key].quantity = qty;
        markUnsavedChanges();
    }
    // Removed the delete logic completely
    renderOrderTable();
    updateOrderStats();
    updateSaveButton();
}

// Function to show delete confirmation modal
let itemToDelete = null;
function confirmDeleteItem(key, varName) {
    itemToDelete = key;
    document.getElementById('delete-item-name').textContent = varName;
    document.getElementById('delete-confirm-modal').style.display = 'block';
}

// Function to close delete confirmation modal
function closeDeleteModal() {
    document.getElementById('delete-confirm-modal').style.display = 'none';
    itemToDelete = null;
}

// Function to confirm deletion
function confirmDeletion() {
    if (itemToDelete) {
        delete orderItems[itemToDelete];
        renderOrderTable();
        updateOrderStats();
        updateSaveButton();
        markUnsavedChanges();
        closeDeleteModal();
    }
}

// Function to switch lookup type
function switchLookupType(type) {
    currentLookupType = type;
    document.getElementById('lookup-variety-btn').classList.toggle('active', type === 'variety');
    document.getElementById('lookup-crop-btn').classList.toggle('active', type === 'crop');
    
    const searchBox = document.getElementById('variety-search');
    searchBox.placeholder = type === 'variety' ? 'Search varieties by name...' : 'Search by crop type...';
    
    // Clear search input when switching types
    clearSearchInput();
}

// Function to search items - FIXED FOR CROP SEARCH
function searchItems(searchTerm) {
    const resultsContainer = document.getElementById('lookup-results');
    
    if (!searchTerm.trim()) {
        resultsContainer.innerHTML = `<div class="no-results"><p>Start typing to search</p></div>`;
        return;
    }

    const searchLower = searchTerm.toLowerCase();
    let matches = [];

    if (currentLookupType === 'variety') {
        matches = Object.entries(varietyData).filter(([skuPrefix, data]) => {
            return data.common_spelling.toLowerCase().includes(searchLower) ||
                    data.var_name.toLowerCase().includes(searchLower);
        });
    } else {
        // FIXED: Get ALL varieties that match the crop type, not just one per type
        matches = Object.entries(varietyData).filter(([skuPrefix, data]) => {
            return data.crop.toLowerCase().includes(searchLower);
        });
    }

    if (matches.length === 0) {
        resultsContainer.innerHTML = `
            <div class="no-results">
                <p>No ${currentLookupType === 'variety' ? 'varieties' : 'crops'} found</p>
                <small>Try a different search term</small>
            </div>
        `;
        return;
    }

    let resultsHTML = '';
    if (currentLookupType === 'variety') {
        resultsHTML = matches.map(([skuPrefix, data]) => `
            <div class="variety-item" onclick="openVarietyModal('${skuPrefix}', ${JSON.stringify(data).replace(/"/g, '&quot;')})">
                <div class="variety-name">${data.var_name}</div>
                <div class="variety-details">
                    <span class="variety-crop">${data.crop}</span>
                </div>
            </div>
        `).join('');
    } else {
        // FIXED: Group by crop type but show ALL varieties
        const cropGroups = {};
        matches.forEach(([skuPrefix, data]) => {
            if (!cropGroups[data.crop]) {
                cropGroups[data.crop] = [];
            }
            cropGroups[data.crop].push([skuPrefix, data]);
        });

        resultsHTML = Object.entries(cropGroups).map(([crop, varieties]) => `
            <div class="variety-item" onclick="toggleCropVarieties('${crop.replace(/[^a-zA-Z0-9]/g, '_')}')">
                <div class="variety-name">${crop}</div>
                <div class="variety-details">
                    <span class="variety-group">${varieties.length} varieties</span>
                </div>
            </div>
            <div id="crop-${crop.replace(/[^a-zA-Z0-9]/g, '_')}-varieties" style="display: none; margin-left: 20px; border-left: 2px solid #e1e5e9;">
                ${varieties.map(([skuPrefix, data]) => `
                    <div class="variety-item" onclick="openVarietyModal('${skuPrefix}', ${JSON.stringify(data).replace(/"/g, '&quot;')})">
                        <div class="variety-name" style="font-size: 0.9rem;">${data.var_name}</div>
                    </div>
                `).join('')}
            </div>
        `).join('');
    }

    resultsContainer.innerHTML = resultsHTML;
}

// Function to toggle crop varieties display - FIXED ID GENERATION
function toggleCropVarieties(crop) {
    const varietiesDiv = document.getElementById(`crop-${crop.replace(/[^a-zA-Z0-9]/g, '_')}-varieties`);
    if (varietiesDiv) {
        varietiesDiv.style.display = varietiesDiv.style.display === 'none' ? 'block' : 'none';
    }
}

// Function to open variety modal
function openVarietyModal(skuPrefix, varietyData) {
    // NEW: Check if no order is selected
    if (!currentOrderId) {
        showNotification('No Order Selected', 
            'Please select a pending order before adding varieties', 
            'warning', '⚠️');
        return;
    }

    // Check if order is finalized
    const isFinalized = currentOrderData && 
                    currentOrderData.fulfilled_date && 
                    currentOrderData.fulfilled_date !== null && 
                    currentOrderData.fulfilled_date.trim() !== '';

    if (isFinalized) {
        showNotification('Order Finalized', 
            'This order has been finalized and cannot be edited', 
            'error', '🔒');
        return;
    }

    // NEW: Check if variety already exists in order
    if (orderItems[skuPrefix]) {
        showNotification('Variety Already Added', 
            'This variety is already in the order', 
            'error', '⚠️');
        return;
    }

    selectedVariety = { sku_prefix: skuPrefix, data: varietyData };
    document.getElementById('selected-variety-name').textContent = varietyData.var_name;
    document.getElementById('variety-qty').value = 1;
    document.getElementById('variety-photo').checked = false;
    document.getElementById('add-variety-modal').style.display = 'block';
}

// Function to close variety modal
function closeVarietyModal() {
    document.getElementById('add-variety-modal').style.display = 'none';
    selectedVariety = null;
}

// Function to save variety to order
async function saveVarietyToOrder() {
    if (!selectedVariety) return;

    const quantity = parseInt(document.getElementById('variety-qty').value);
    const hasPhoto = document.getElementById('variety-photo').checked;

    // if (quantity < 0) {
    //     alert('Quantity must be at least 0');
    //     return;
    // }

    const key = selectedVariety.sku_prefix;
    const data = selectedVariety.data;

    if (orderItems[key]) {
        orderItems[key].quantity += quantity;
        orderItems[key].hasPhoto = orderItems[key].hasPhoto || hasPhoto;
    } else {
        orderItems[key] = {
            sku_prefix: key,
            var_name: data.var_name,
            crop: data.crop,
            quantity: quantity,
            hasPhoto: hasPhoto,
            category: data.category
        };
    }

    renderOrderTable();
    updateOrderStats();
    updateSaveButton();
    closeVarietyModal();

    // Auto-save when adding new items
    if (currentOrderId) {
        await saveOrderChanges();
        showNotification('Item Added!', `${data.var_name} has been added and saved automatically`);
    } else {
        markUnsavedChanges();
        showNotification('Item Added!', `${data.var_name} has been added to order`);
    }
}

// Function to load order details and populate order builder
async function loadOrderDetails(orderId) {
    try {
        const response = await fetch(`/office/get-order-details/${orderId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            alert(`Error loading order: ${data.error}`);
            return;
        }
        
        // Clear current order items and unsaved changes
        orderItems = {};
        currentOrderId = orderId;
        currentOrderData = data.order || null; // Store order data including fulfilled_date
        hasUnsavedChanges = false; // Clear unsaved changes when loading order
        
        // Debug logging
        console.log('Loading order details:', {
            orderId: orderId,
            currentOrderData: currentOrderData,
            isFinalized: currentOrderData && currentOrderData.fulfilled_date
        });
        
        // Populate with order items
        if (data.items && data.items.length > 0) {
            data.items.forEach(item => {
                orderItems[item.sku_prefix] = {
                    sku_prefix: item.sku_prefix,
                    var_name: item.var_name,
                    crop: item.crop,
                    quantity: item.quantity,
                    hasPhoto: item.has_photo || false,
                    category: item.category
                };
            });
        }
        
        // Check if order is finalized (has fulfilled_date)
        const isFinalized = currentOrderData && 
                            currentOrderData.fulfilled_date && 
                            currentOrderData.fulfilled_date !== null && 
                            currentOrderData.fulfilled_date.trim() !== '';
        
        // Update the UI
        renderOrderTable(isFinalized); // Pass read-only flag if finalized
        updateOrderStats();
        updateSaveButton(); // This will now properly check if order is finalized
        updateUnsavedIndicator(); // Update the unsaved changes indicator
        
        // Show notification if order is finalized
        if (isFinalized) {
            showNotification('Viewing Finalized Order', 
                `This order was completed on ${formatDate(currentOrderData.fulfilled_date)}`, 'success', '📋');
        }
        
    } catch (error) {
        console.error('Error loading order details:', error);
        alert('Error loading order details. Please try again.');
    }
}

// Helper function to format date
function formatDate(dateString) {
    if (!dateString) return '';
    try {
        return new Date(dateString).toLocaleDateString();
    } catch {
        return dateString;
    }
}

// Function to handle order selection from dropdown
function handleOrderSelection(event) {
    const orderId = event.target.value;
    if (orderId) {
        loadOrderDetails(orderId);
    } else {
        clearOrderBuilder();
    }
}

// Function to save order changes
async function saveOrderChanges() {
    if (!currentOrderId) return;

    const saveBtn = document.getElementById('save-order-btn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const response = await fetch(`/office/save-order-changes/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                order_id: currentOrderId,
                items: Object.values(orderItems).map(item => ({
                    sku_prefix: item.sku_prefix,
                    quantity: item.quantity,
                    has_photo: item.hasPhoto
                }))
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            alert(`Error saving order: ${data.error}`);
        } else {
            markChangesSaved();
            showNotification('Order Saved!', `Successfully updated ${Object.keys(orderItems).length} items`);
        }

    } catch (error) {
        console.error('Error saving order:', error);
        alert('Error saving order. Please try again.');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Changes';
    }
}

// Function to open pending orders modal
function openPendingOrdersModal() {
    document.getElementById('pending-orders-modal').style.display = 'block';
    loadPendingOrders();
}

// Function to close pending orders modal
function closePendingOrdersModal() {
    document.getElementById('pending-orders-modal').style.display = 'none';
}


// Replace your loadPendingOrders function with this:
async function loadPendingOrders() {
    const container = document.getElementById('pending-orders-container');
    
    try {
        const response = await fetch('/office/get-pending-orders/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            container.innerHTML = `
                <div class="no-pending-orders">
                    <div class="no-pending-icon">❌</div>
                    <p>Error loading pending orders</p>
                    <small>${data.error}</small>
                </div>
            `;
            return;
        }
        
        if (!data.orders || data.orders.length === 0) {
            container.innerHTML = `
                <div class="no-pending-orders">
                    <div class="no-pending-icon">✅</div>
                    <p>No pending orders</p>
                    <small>All orders are fulfilled!</small>
                </div>
            `;
            return;
        }
        
        // Clear selected orders when reloading
        selectedOrdersForCombine.clear();
        
        // Add combine button and selected count at the top
        let ordersHTML = `
            <div style="margin-bottom: 15px; padding: 0 10px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                <button class="btn" id="combine-orders-btn" style="background: #667eea; display: none;">
                    Combine Selected Orders
                </button>
                <span id="selected-count" style="color: #666; font-size: 0.9rem; display: none;"></span>
            </div>
            <div class="pending-orders-list">
        `;
        
        data.orders.forEach(order => {
            console.log('Pending order object:', order);
            
            // Extract store number from order number (format: WXXYY-ZZ where XX is store number)
            const storeNumMatch = order.order_number.match(/^W(\d{2})/);
            const storeNum = storeNumMatch ? storeNumMatch[1] : (order.store_id || order.store_num || '');
            
            ordersHTML += `
                <div class="pending-order-item" data-order-id="${order.id}" data-store-id="${storeNum}" data-store-name="${order.store_name}" style="position: relative; padding-left: 40px;">
                    <input 
                        type="checkbox" 
                        class="order-combine-checkbox" 
                        data-order-number="${order.order_number}"
                        data-store-num="${storeNum}"
                        style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); width: 18px; height: 18px; cursor: pointer;"
                    >
                    <div onclick="loadPendingOrderByNumber('${order.order_number}')" style="cursor: pointer; flex: 1;">
                        <div class="pending-order-number">Order #${order.order_number}</div>
                        <div class="pending-order-details">
                            <span class="pending-order-store">${order.store_name}</span>
                            <span class="pending-order-date">${order.date}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        ordersHTML += '</div>';
        
        container.innerHTML = ordersHTML;
        
        // Add event listeners to checkboxes
        document.querySelectorAll('.order-combine-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', handleCombineCheckboxChange);
            // Stop click events from bubbling up to parent
            checkbox.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        });
        
        // Add event listener to combine button
        const combineBtn = document.getElementById('combine-orders-btn');
        if (combineBtn) {
            combineBtn.addEventListener('click', handleCombineOrders);
        }
        
    } catch (error) {
        console.error('Error loading pending orders:', error);
        container.innerHTML = `
            <div class="no-pending-orders">
                <div class="no-pending-icon">❌</div>
                <p>Error loading pending orders</p>
                <small>Please try again</small>
            </div>
        `;
    }
}

async function loadPendingOrderByNumber(orderNumber) {
    // Close the modal
    document.getElementById('pending-orders-modal').style.display = 'none';
    
    // Find the order data from the pending orders list to get the order ID
    const orderItem = document.querySelector(`[data-order-number="${orderNumber}"]`);
    if (!orderItem) {
        console.error('Could not find order item for:', orderNumber);
        return;
    }
    
    const orderId = orderItem.closest('.pending-order-item').dataset.orderId;
    const storeId = orderItem.dataset.storeNum;
    const storeName = orderItem.closest('.pending-order-item').dataset.storeName;
    
    console.log('Loading order:', { orderNumber, orderId, storeId, storeName });
    
    // Use your existing loadOrderFromPending function
    await loadOrderFromPending(orderId, storeId, storeName);
}


// Checkbox change handler
function handleCombineCheckboxChange(e) {
    const checkbox = e.target;
    const orderNumber = checkbox.dataset.orderNumber;
    
    if (checkbox.checked) {
        selectedOrdersForCombine.add(orderNumber);
    } else {
        selectedOrdersForCombine.delete(orderNumber);
    }
    
    updateCombineButton();
}

// Update combine button visibility
function updateCombineButton() {
    const combineBtn = document.getElementById('combine-orders-btn');
    const selectedCount = document.getElementById('selected-count');
    
    if (selectedOrdersForCombine.size >= 2) {
        combineBtn.style.display = 'block';
        selectedCount.style.display = 'inline';
        selectedCount.textContent = `${selectedOrdersForCombine.size} orders selected`;
    } else {
        combineBtn.style.display = 'none';
        selectedCount.style.display = 'none';
    }
}








async function handleCombineOrders() {
    const orderNumbers = Array.from(selectedOrdersForCombine);
    
    // Verify all selected orders are from the same store
    const checkboxes = document.querySelectorAll('.order-combine-checkbox:checked');
    const storeNums = new Set();
    checkboxes.forEach(cb => storeNums.add(cb.dataset.storeNum));
    
    if (storeNums.size > 1) {
        showNotification('Error: Selected orders do not belong to the same store', 'error');
        return;
    }
    
    // Sort order numbers to find the target (lowest)
    const sortedOrders = orderNumbers.sort();
    const targetOrder = sortedOrders[0];
    
    // Show custom confirmation modal
    showCombineConfirmation(sortedOrders, targetOrder);
}

// New function to show the combine confirmation modal
function showCombineConfirmation(orderNumbers, targetOrder) {
    const modal = document.getElementById('combine-confirm-modal');
    const countEl = document.getElementById('combine-count');
    const targetEl = document.getElementById('combine-target-order');
    const listEl = document.getElementById('combine-order-list');
    
    // Update modal content
    countEl.textContent = orderNumbers.length;
    targetEl.textContent = targetOrder;
    
    // Build order list HTML
    let listHTML = '<div style="font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; color: #666;">Orders to combine:</div>';
    orderNumbers.forEach((orderNum, index) => {
        const isTarget = orderNum === targetOrder;
        listHTML += `
            <div style="padding: 8px; margin-bottom: 6px; background: ${isTarget ? '#e7f3ff' : '#fff'}; border-radius: 6px; border: ${isTarget ? '2px solid #667eea' : '1px solid #e1e5e9'}; display: flex; align-items: center; gap: 8px;">
                ${isTarget ? '<span style="color: #667eea; font-size: 1.2rem;">→</span>' : '<span style="color: #999;">•</span>'}
                <span style="font-family: monospace; font-weight: ${isTarget ? '600' : '400'};">${orderNum}</span>
                ${isTarget ? '<span style="margin-left: auto; background: #667eea; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">TARGET</span>' : ''}
            </div>
        `;
    });
    listEl.innerHTML = listHTML;
    
    // Show modal
    modal.style.display = 'block';
    
    // Set up event handlers
    const closeBtn = document.getElementById('close-combine-modal');
    const cancelBtn = document.getElementById('cancel-combine-btn');
    const confirmBtn = document.getElementById('confirm-combine-btn');
    
    const closeModal = () => {
        modal.style.display = 'none';
    };
    
    closeBtn.onclick = closeModal;
    cancelBtn.onclick = closeModal;
    
    confirmBtn.onclick = async () => {
        closeModal();
        await executeCombineOrders(orderNumbers);
    };
    
    // Close on outside click
    window.onclick = (event) => {
        if (event.target === modal) {
            closeModal();
        }
    };
}

// New function to execute the actual combine
async function executeCombineOrders(orderNumbers) {
    try {
        const response = await fetch('/office/combine-orders/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                order_numbers: orderNumbers
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(data.message, 'success');
            selectedOrdersForCombine.clear();
            // Reload pending orders
            loadPendingOrders();
            // Load the combined order
            loadPendingOrderByNumber(data.target_order);
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        console.error('Error combining orders:', error);
        showNotification('Failed to combine orders', 'error');
    }
}


function loadPendingOrder(orderNumber) {
    // Close the modal
    document.getElementById('pending-orders-modal').style.display = 'none';
    
    // Extract store number from order number (format: WXXYY-ZZ)
    const storeNumMatch = orderNumber.match(/^W(\d{2})/);
    if (storeNumMatch) {
        const storeNum = parseInt(storeNumMatch[1], 10);
        
        // Set the store filter
        const storeFilter = document.getElementById('store-filter');
        storeFilter.value = storeNum;
        
        // Trigger the store filter change to load orders - this is async!
        const storeChangeEvent = new Event('change');
        storeFilter.dispatchEvent(storeChangeEvent);
        
        // Wait longer for orders to populate (loadOrdersForStore is async)
        setTimeout(() => {
            const orderFilter = document.getElementById('order-filter');
            
            // Double check the order is in the dropdown
            const orderOption = Array.from(orderFilter.options).find(opt => opt.value === orderNumber);
            
            if (orderOption) {
                orderFilter.value = orderNumber;
                
                // Trigger the order filter change to load the order
                const orderChangeEvent = new Event('change');
                orderFilter.dispatchEvent(orderChangeEvent);
            } else {
                console.error('Order not found in dropdown:', orderNumber);
                // Fallback: load the order directly
                loadOrder(orderNumber);
            }
        }, 500); // Increased from 300ms to 500ms
    }
}


// Update showNotification to handle error type
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    const messageEl = notification.querySelector('.notification-message');
    const icon = notification.querySelector('.notification-icon');
    
    messageEl.textContent = message;
    
    if (type === 'error') {
        notification.style.background = 'linear-gradient(135deg, #ff6b6b, #ee5a52)';
        icon.textContent = '⚠';
    } else {
        notification.style.background = 'linear-gradient(135deg, #26de81, #20bf6b)';
        icon.textContent = '✓';
    }
    
    notification.classList.add('show');
    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}










// Function to load order from pending orders modal
async function loadOrderFromPending(orderId, storeId, storeName) {
    console.log('=== LOAD ORDER FROM PENDING ===');
    console.log('Order ID:', orderId);
    console.log('Store ID:', storeId);
    console.log('Store Name:', storeName);
    
    closePendingOrdersModal();
    
    const storeFilter = document.getElementById('store-filter');
    console.log('Available store options:', Array.from(storeFilter.options).map(opt => ({value: opt.value, text: opt.text})));
    
    let finalStoreId = storeId;
    
    // If no store ID provided, try to find it by matching store name
    if (!storeId && storeName) {
        console.log('No store ID provided, trying to match by store name:', storeName);
        const matchingOption = Array.from(storeFilter.options).find(option => 
            option.text.toLowerCase().includes(storeName.toLowerCase()) ||
            storeName.toLowerCase().includes(option.text.toLowerCase())
        );
        
        if (matchingOption) {
            finalStoreId = matchingOption.value;
            console.log('Found matching store by name. Store ID:', finalStoreId);
        } else {
            console.error('Could not find matching store for name:', storeName);
            alert(`Error: Could not find store "${storeName}" in dropdown. Please select the store manually.`);
            await loadOrderDetails(orderId);
            return;
        }
    }
    
    console.log('Final store ID to use:', finalStoreId);
    
    // Set the store filter
    storeFilter.value = finalStoreId;
    currentStore = finalStoreId;
    
    console.log('Store filter value after setting:', storeFilter.value);
    
    // If store filter is still empty, we couldn't match it
    if (!storeFilter.value) {
        console.error('Could not set store filter to:', finalStoreId);
        alert(`Error: Could not select store. Please select the store manually.`);
        await loadOrderDetails(orderId);
        return;
    }
    
    // Load orders for this store
    const orderFilter = document.getElementById('order-filter');
    orderFilter.disabled = false;
    orderFilter.innerHTML = '<option value="">Loading orders...</option>';
    
    try {
        console.log('Fetching orders for store:', finalStoreId);
        const response = await fetch(`/office/get-store-orders/${finalStoreId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
        });
        
        console.log('Store orders response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Store orders data:', data);
        
        if (data.error) {
            console.error('Backend error:', data.error);
            orderFilter.innerHTML = '<option value="">Error loading orders</option>';
            return;
        }
        
        if (!data.orders || data.orders.length === 0) {
            console.log('No orders found for store');
            orderFilter.innerHTML = '<option value="">No orders found</option>';
            return;
        }
        
        // Build options HTML
        let optionsHTML = '<option value="">Select Order</option>';
        data.orders.forEach(order => {
            const prefix = order.is_pending ? 'P ' : '';
            optionsHTML += `<option value="${order.id}">${prefix}Order #${order.order_number} - ${order.date}</option>`;
        });
        orderFilter.innerHTML = optionsHTML;
        
        console.log('Available order options:', Array.from(orderFilter.options).map(opt => ({value: opt.value, text: opt.text})));
        console.log('Attempting to set order filter to:', orderId);
        
        // Set the order filter to the selected order
        orderFilter.value = orderId.toString();
        console.log('Order filter value after setting:', orderFilter.value);
        
        if (!orderFilter.value) {
            console.error('Order ID not found in dropdown options:', orderId);
        }
        
    } catch (error) {
        console.error('Error loading store orders:', error);
        orderFilter.innerHTML = '<option value="">Error loading orders</option>';
    }
    
    // Load the order details
    console.log('Loading order details for order:', orderId);
    await loadOrderDetails(orderId);
}

// Function to handle store filter change
async function handleStoreFilterChange(event) {
    console.log('=== STORE FILTER CHANGE ===');
    const storeId = event.target.value;
    console.log('Previous store:', currentStore);
    console.log('New store:', storeId);
    
    // Clear order builder when switching stores
    if (currentStore !== storeId) {
        console.log('Clearing order builder - store changed');
        clearOrderBuilder();
    }
    
    currentStore = storeId;
    const orderFilter = document.getElementById('order-filter');
    
    // Reset order dropdown selection
    orderFilter.value = '';
    
    if (storeId) {
        console.log('Loading orders for store:', storeId);
        orderFilter.disabled = false;
        orderFilter.innerHTML = '<option value="">Loading orders...</option>';
        
        try {
            const response = await fetch(`/office/get-store-orders/${storeId}/`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Content-Type': 'application/json',
                },
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                orderFilter.innerHTML = '<option value="">Error loading orders</option>';
                return;
            }
            
            if (!data.orders || data.orders.length === 0) {
                orderFilter.innerHTML = '<option value="">No orders found</option>';
                return;
            }
            
            let optionsHTML = '<option value="">Select Order</option>';
            data.orders.forEach(order => {
                const prefix = order.is_pending ? 'P ' : '';
                optionsHTML += `<option value="${order.id}">${prefix}Order #${order.order_number} - ${order.date}</option>`;
            });
            orderFilter.innerHTML = optionsHTML;
        } catch (error) {
            console.error('Error fetching orders:', error);
            orderFilter.innerHTML = '<option value="">Error loading orders</option>';
        }
    } else {
        console.log('All stores selected - clearing order builder');
        orderFilter.disabled = true;
        orderFilter.innerHTML = '<option value="">Select Order</option>';
    }
}

// Function to show success notification
function showNotification(title = 'Success!', message = 'Operation completed successfully', type = 'success', icon = '✓') {
    const notification = document.getElementById('notification');
    const titleElement = notification.querySelector('.notification-title');
    const messageElement = notification.querySelector('.notification-message');
    const iconElement = notification.querySelector('.notification-icon');
    
    titleElement.textContent = title;
    messageElement.textContent = message;
    iconElement.textContent = icon;
    
    // Remove existing type classes and add the appropriate one
    notification.classList.remove('error');
    if (type === 'error') {
        notification.classList.add('error');
    }
    
    notification.classList.add('show');
    
    // Auto-hide after 6 seconds for errors, 4 seconds for success
    setTimeout(() => {
        hideNotification();
    }, type === 'error' ? 6000 : 4000);
}

// Function to hide notification
function hideNotification() {
    const notification = document.getElementById('notification');
    notification.classList.remove('show');
}

// Function to call Flask app for invoice printing (DUMMY FOR NOW)
async function callFlaskForInvoice(orderData) {
    try {
        console.log('Calling Flask app for invoice printing with data:', orderData);
        
        // DUMMY IMPLEMENTATION - just simulate success
        await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay
        console.log('Flask app call completed successfully (dummy)');
        return { success: true, message: 'Invoice printed' };
        
        // ACTUAL FLASK IMPLEMENTATION (commented out for now)
        /*
        const response = await fetch('http://localhost:5000/print-invoice', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(orderData)
        });
        
        if (!response.ok) {
            throw new Error(`Flask app responded with status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('Flask response:', result);
        return result;
        */
        
    } catch (error) {
        console.error('Flask app error:', error);
        
        // Show error notification
        showNotification('Print Service Unavailable', 
            'Could not connect to the printing service. The order has been finalized but no invoice was printed.',
            'error', '⚠️');
        
        throw error;
    }
}

// Function to open finalize confirmation modal
function openFinalizeConfirmModal() {
    if (!currentOrderId) {
        alert('No order selected to finalize');
        return;
    }

    if (Object.keys(orderItems).length === 0) {
        alert('Cannot finalize an empty order');
        return;
    }

    // Update the summary in the modal
    const uniqueItems = Object.keys(orderItems).length;
    const totalPackets = Object.values(orderItems).reduce((sum, item) => sum + item.quantity, 0);
    
    document.getElementById('finalize-items-count').textContent = `${uniqueItems} unique varieties`;
    document.getElementById('finalize-packets-count').textContent = `${totalPackets} total packets`;
    
    document.getElementById('finalize-confirm-modal').style.display = 'block';
}

// Function to close finalize confirmation modal
function closeFinalizeConfirmModal() {
    document.getElementById('finalize-confirm-modal').style.display = 'none';
}




async function handlePickListClick() {
    if (!currentOrderId) {
        showNotification('No Order Selected', 'Please select an order first', 'error', '📋');
        return;
    }

    if (Object.keys(orderItems).length === 0) {
        showNotification('Empty Order', 'Cannot generate pick list for empty order', 'error', '📦');
        return;
    }

    // Check if order is already finalized
    const isFinalized = currentOrderData && 
                    currentOrderData.fulfilled_date && 
                    currentOrderData.fulfilled_date !== null && 
                    currentOrderData.fulfilled_date.trim() !== '';

    if (isFinalized) {
        showNotification('Order Already Finalized', 
            `This order was completed on ${formatDate(currentOrderData.fulfilled_date)}. Pick lists cannot be generated for finalized orders.`,
            'error', '🔒');
        return;
    }

    // Check if pick list has already been printed
    try {
        const response = await fetch(`/office/check-pick-list-printed/${currentOrderId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.already_printed) {
            // Show confirmation modal
            document.getElementById('pick-list-confirm-modal').style.display = 'block';
            return;
        }

        // Not printed yet, proceed directly
        await proceedWithPickList();

    } catch (error) {
        console.error('Error checking pick list status:', error);
        showNotification('Error', 'Failed to check pick list status', 'error', '❌');
    }
}

// Function to close pick list confirmation modal
function closePickListConfirmModal() {
    document.getElementById('pick-list-confirm-modal').style.display = 'none';
}

// Function to proceed with pick list generation
async function proceedWithPickList() {
    // Check Flask health
    const flaskHealthy = await checkFlaskHealth();
    if (!flaskHealthy) {
        showNotification('Print Service Unavailable', 
            'The Flask printing service is not running. Please start the Flask service and try again.',
            'error', '🖨️');
        return;
    }

    // Generate the pick list
    await generatePickList();
}

// Updated generatePickList function to record the print
async function generatePickList() {
    try {
        // // Prepare pick list data
        // const pickListItems = Object.values(orderItems).map(item => ({
        //     variety_name: item.var_name,
        //     crop: item.crop,
        //     quantity: item.quantity,
        //     has_photo: item.hasPhoto
        // }));
        // Prepare pick list data - use sorted order from the UI
        const sortedItems = sortOrderItems(orderItems);
        const pickListItems = sortedItems.map(([key, item]) => ({
            variety_name: item.var_name,
            crop: item.crop,
            quantity: item.quantity,
            has_photo: item.hasPhoto,
            rack_location: item.rack_location || null  // Include rack_location if available
        }));

        const pickListData = {
            order_id: currentOrderId,
            order_number: currentOrderData?.order_number || 'Unknown',
            store_name: currentOrderData?.store_name || 'Unknown',
            items: pickListItems
        };

        // Send to Flask
        const response = await fetch(`${FLASK_BASE_URL}/print-pick-list`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(pickListData)
        });

        if (!response.ok) {
            throw new Error(`Flask responded with status: ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            // Record the print in Django
            await recordPickListPrinted();
            
            showNotification('Pick List Generated', 
                `Pick list for ${pickListItems.length} items sent to printer`,
                'success', '✓');
        } else {
            throw new Error(result.error || 'Unknown error');
        }

    } catch (error) {
        console.error('Error generating pick list:', error);
        showNotification('Pick List Error', 
            `Failed to generate pick list: ${error.message}`,
            'error', '❌');
    }
}

// Function to record pick list as printed
async function recordPickListPrinted() {
    try {
        const response = await fetch('/office/record-pick-list-printed/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                order_id: currentOrderId
            })
        });

        if (!response.ok) {
            console.error('Failed to record pick list print');
        }
    } catch (error) {
        console.error('Error recording pick list print:', error);
    }
}


// NEW FUNCTION - Send order data to Flask for invoice printing
async function printStoreOrderInvoice(orderData) {
    try {
        console.log('=== PRINT STORE ORDER INVOICE ===');
        console.log('Order data received:', orderData);
        console.log('Shipping from order data:', orderData.order.shipping);
        
        const invoiceData = {
            order: {
                order_number: orderData.order.order_number,
                date: orderData.order.date,
                fulfilled_date: orderData.order.fulfilled_date,
                notes: orderData.order.notes,
                shipping: orderData.order.shipping,
                credit: orderData.order.credit
            },
            store: {
                store_name: orderData.store.store_name,
                contact_name: orderData.store.store_contact_name,
                contact_phone: orderData.store.store_contact_phone,
                contact_email: orderData.store.store_contact_email,
                address: orderData.store.store_address,
                address2: orderData.store.store_address2,
                city: orderData.store.store_city,
                state: orderData.store.store_state,
                zip: orderData.store.store_zip
            },
            items: orderData.items.map(item => ({
                variety_name: item.variety_name,
                crop: item.crop,
                quantity: item.quantity,
                has_photo: item.has_photo,
                price: item.price
            }))
        };

        console.log('Invoice data being sent to Flask:', invoiceData);
        console.log('Shipping in invoice data:', invoiceData.order.shipping);

        const response = await fetch(`${FLASK_BASE_URL}/print-store-order-invoice`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(invoiceData)
        });

        if (!response.ok) {
            throw new Error(`Flask responded with status: ${response.status}`);
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Unknown error');
        }

        console.log('Invoice printed successfully');

    } catch (error) {
        console.error('Flask invoice printing error:', error);
        throw error;
    }
}

// Function to show shipping modal
function showShippingModal() {
    document.getElementById('shipping-modal').style.display = 'block';
    document.getElementById('shipping-amount').value = '0.00';
    document.getElementById('shipping-error').style.display = 'none';
    // Focus on input field
    setTimeout(() => {
        document.getElementById('shipping-amount').focus();
    }, 100);
}

// Function to close shipping modal
function closeShippingModal() {
    document.getElementById('shipping-modal').style.display = 'none';
    document.getElementById('shipping-amount').value = '';
    document.getElementById('shipping-error').style.display = 'none';
}

// Function to validate and process shipping input
function validateAndProcessShipping() {
    const shippingInput = document.getElementById('shipping-amount').value.trim();
    const errorDiv = document.getElementById('shipping-error');
    
    // Remove any dollar signs if user entered them
    const cleanInput = shippingInput.replace('$', '').trim();
    
    // Validate floating point number
    const floatRegex = /^\d+\.?\d{0,2}$/;
    
    if (!floatRegex.test(cleanInput)) {
        errorDiv.style.display = 'block';
        return false;
    }
    
    const shippingAmount = parseFloat(cleanInput);
    
    if (isNaN(shippingAmount) || shippingAmount < 0) {
        errorDiv.style.display = 'block';
        return false;
    }
    
    // Valid input - store it and proceed
    currentShippingCost = shippingAmount;
    closeShippingModal();
    
    // Continue to finalize confirmation modal
    openFinalizeConfirmModal();
    
    return true;
}

// Function to finalize order (called from modal confirmation)
async function finalizeOrder() {
    const finalizeBtn = document.getElementById('confirm-finalize-btn');
    const cancelBtn = document.getElementById('cancel-finalize-btn');
    
    finalizeBtn.disabled = true;
    cancelBtn.disabled = true;
    finalizeBtn.textContent = 'Finalizing...';

    try {
        // First save any unsaved changes
        if (hasUnsavedChanges) {
            await saveOrderChanges();
        }

        console.log('=== FINALIZE ORDER ===');
        console.log('Order ID:', currentOrderId);
        console.log('Shipping cost being sent to Django:', currentShippingCost);
        
        // Call backend to finalize order
        const response = await fetch(`/office/finalize-order/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                order_id: currentOrderId,
                shipping: currentShippingCost,
                items: Object.values(orderItems).map(item => ({
                    sku_prefix: item.sku_prefix,
                    quantity: item.quantity,
                    has_photo: item.hasPhoto
                }))
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        console.log('Data received from Django:', data);
        console.log('Shipping in returned data:', data.order.shipping);

        // Update currentOrderData with fulfilled_date
        if (currentOrderData) {
            currentOrderData.fulfilled_date = data.order.fulfilled_date;
        }

        // Close the confirmation modal
        closeFinalizeConfirmModal();

        // Send to Flask for invoice printing
        try {
            console.log('Sending to Flask...');
            await printStoreOrderInvoice(data);
            
            showNotification('Order Finalized!', 
                `Order #${data.order.order_number} has been finalized and invoice sent to printer`);
        } catch (flaskError) {
            console.log('Flask call failed, but order was finalized successfully');
            showNotification('Order Finalized!', 
                `Order #${data.order.order_number} has been finalized successfully`);
        }

        // Re-render table in read-only mode and update UI
        renderOrderTable(true);
        updateSaveButton();
        refreshOrderDropdowns();

    } catch (error) {
        console.error('Error finalizing order:', error);
        showNotification('Finalization Error', 
            `Failed to finalize order: ${error.message}`,
            'error', '❌');
        
        // Re-enable modal buttons
        finalizeBtn.disabled = false;
        cancelBtn.disabled = false;
        finalizeBtn.textContent = 'Finalize Order';
    }
}





// Function to initiate finalize process (called by finalize button)
async function initiateFinalizeOrder() {
    if (!currentOrderId) {
        showNotification('No Order Selected', 'Please select an order to finalize', 'error', '📋');
        return;
    }

    if (Object.keys(orderItems).length === 0) {
        showNotification('Empty Order', 'Cannot finalize an empty order', 'error', '📦');
        return;
    }

    // Check if order is already finalized
    const isFinalized = currentOrderData && 
                    currentOrderData.fulfilled_date && 
                    currentOrderData.fulfilled_date !== null && 
                    currentOrderData.fulfilled_date.trim() !== '';

    if (isFinalized) {
        showNotification('Order Already Finalized', 
            `This order was completed on ${formatDate(currentOrderData.fulfilled_date)} and cannot be finalized again`, 
            'error', '🔒');
        return;
    }

    // Check Flask health BEFORE showing the modal
    const flaskHealthy = await checkFlaskHealth();
    if (!flaskHealthy) {
        showNotification('Print Service Unavailable', 
            'The Flask printing service is not running. Please start the Flask service and try again.',
            'error', '🖨️');
        return;
    }

    // Show shipping input modal FIRST
    showShippingModal();
}


// Function to disable order editing
function disableOrderEditing() {
    // Disable save button
    const saveBtn = document.getElementById('save-order-btn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Order Finalized';
    saveBtn.style.opacity = '0.5';
    
    // Hide unsaved indicator
    hasUnsavedChanges = false;
    updateUnsavedIndicator();
    
    // Update table to be read-only
    renderOrderTable(true); // Pass true for read-only mode
}

// Function to refresh order dropdowns
async function refreshOrderDropdowns() {
    if (currentStore) {
        // Trigger store change to refresh the order dropdown
        const storeFilter = document.getElementById('store-filter');
        await handleStoreFilterChange({ target: storeFilter });
    }
}
function goToDashboard() {
    window.location.href = "/office/dashboard/";
}


// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded');
    
    // FIXED: Clear search input on page load
    clearSearchInput();
    
    // Store filter change
    document.getElementById('store-filter').addEventListener('change', handleStoreFilterChange);
    
    // Order filter change
    document.getElementById('order-filter').addEventListener('change', handleOrderSelection);
    
    // Search input
    document.getElementById('variety-search').addEventListener('input', function(e) {
        searchItems(e.target.value);
    });

    // Lookup type buttons
    document.getElementById('lookup-variety-btn').addEventListener('click', function() {
        switchLookupType('variety');
    });
    document.getElementById('lookup-crop-btn').addEventListener('click', function() {
        switchLookupType('crop');
    });

    // Button event listeners
    document.getElementById('dashboard-btn').addEventListener('click', goToDashboard);
    document.getElementById('pending-btn').addEventListener('click', openPendingOrdersModal);
    document.getElementById('save-order-btn').addEventListener('click', saveOrderChanges);
    document.getElementById('finalize-btn').addEventListener('click', initiateFinalizeOrder);
    document.getElementById('pick-list-btn').addEventListener('click', handlePickListClick); 
    document.getElementById('close-pick-list-modal').addEventListener('click', closePickListConfirmModal);
    document.getElementById('cancel-pick-list-btn').addEventListener('click', closePickListConfirmModal);
    document.getElementById('close-shipping-modal').addEventListener('click', closeShippingModal);
    document.getElementById('cancel-shipping-btn').addEventListener('click', closeShippingModal);
    document.getElementById('confirm-shipping-btn').addEventListener('click', validateAndProcessShipping);
    document.getElementById('confirm-pick-list-btn').addEventListener('click', async function() {
        closePickListConfirmModal();
        await proceedWithPickList();
    });

    // Modal event listeners
    document.getElementById('close-pending-modal').addEventListener('click', closePendingOrdersModal);
    document.getElementById('close-variety-modal').addEventListener('click', closeVarietyModal);
    document.getElementById('cancel-variety-btn').addEventListener('click', closeVarietyModal);
    document.getElementById('save-variety-btn').addEventListener('click', saveVarietyToOrder);
    
    // Edit item modal event listeners
    document.getElementById('close-edit-modal').addEventListener('click', closeEditItemModal);
    document.getElementById('cancel-edit-btn').addEventListener('click', closeEditItemModal);
    document.getElementById('save-edit-btn').addEventListener('click', saveItemEdits);
    document.getElementById('remove-item-btn').addEventListener('click', removeItemFromEdit);
    
    // Delete confirmation modal event listeners
    document.getElementById('close-delete-modal').addEventListener('click', closeDeleteModal);
    document.getElementById('cancel-delete-btn').addEventListener('click', closeDeleteModal);
    document.getElementById('confirm-delete-btn').addEventListener('click', confirmDeletion);

    // Finalize confirmation modal event listeners
    document.getElementById('close-finalize-modal').addEventListener('click', closeFinalizeConfirmModal);
    document.getElementById('cancel-finalize-btn').addEventListener('click', closeFinalizeConfirmModal);
    document.getElementById('confirm-finalize-btn').addEventListener('click', finalizeOrder);

    // Close modals when clicking outside
    window.addEventListener('click', function(event) {
        const varietyModal = document.getElementById('add-variety-modal');
        const pendingModal = document.getElementById('pending-orders-modal');
        const deleteModal = document.getElementById('delete-confirm-modal');
        const editModal = document.getElementById('edit-item-modal');
        const finalizeModal = document.getElementById('finalize-confirm-modal');
        const pickListModal = document.getElementById('pick-list-confirm-modal');
        const shippingModal = document.getElementById('shipping-modal');
        if (event.target === shippingModal) {
            closeShippingModal();
        }
        if (event.target === pickListModal) {
            closePickListConfirmModal();
        }
        
        if (event.target === varietyModal) {
            closeVarietyModal();
        }
        if (event.target === pendingModal) {
            closePendingOrdersModal();
        }
        if (event.target === deleteModal) {
            closeDeleteModal();
        }
        if (event.target === editModal) {
            closeEditItemModal();
        }
        if (event.target === finalizeModal) {
            closeFinalizeConfirmModal();
        }
    });

    document.getElementById('shipping-amount').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            validateAndProcessShipping();
        }
    });

    // Keyboard shortcuts for closing modals
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeVarietyModal();
            closePendingOrdersModal();
            closeDeleteModal();
            closeEditItemModal();
            closeFinalizeConfirmModal();
            closePickListConfirmModal();  
            closeShippingModal();
        }
    });

    // Add event delegation for pending order items
    document.addEventListener('click', function(e) {
        const pendingItem = e.target.closest('.pending-order-item');
        if (pendingItem && document.getElementById('pending-orders-modal').style.display === 'block') {
            const orderId = parseInt(pendingItem.dataset.orderId);
            const storeId = pendingItem.dataset.storeId;
            const storeName = pendingItem.dataset.storeName;
            loadOrderFromPending(orderId, storeId, storeName);
        }
    });

    // Fix for page reload - trigger store change if store is already selected
    const storeFilter = document.getElementById('store-filter');
    if (storeFilter.value) {
        console.log('Store already selected on load, triggering change');
        setTimeout(() => {
            handleStoreFilterChange({ target: storeFilter });
        }, 100);
    }

    // Initialize
    updateOrderStats();
    updateSaveButton();
});