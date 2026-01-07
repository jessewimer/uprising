// Global variables
let currentStoreId = null;
let currentStoreNum = null;
let currentSelectedYear = null;
let returnsData = [];

// CSRF token helper - read from meta tag
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

document.addEventListener('DOMContentLoaded', function() {
    // Handle column toggle buttons
    const toggleBtns = document.querySelectorAll('.toggle-btn');
    const tableWrapper = document.getElementById('tableWrapper');
    
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const group = this.dataset.group;
            const isActive = this.classList.contains('active');
            
            if (isActive) {
                this.classList.remove('active');
                tableWrapper.classList.remove(`show-${group}`);
                tableWrapper.classList.add(`hide-${group}`);
            } else {
                this.classList.add('active');
                tableWrapper.classList.remove(`hide-${group}`);
                tableWrapper.classList.add(`show-${group}`);
            }
        });
    });

    // Handle edit button clicks
    document.addEventListener('click', function(e) {
        if (e.target.closest('.edit-btn')) {
            const btn = e.target.closest('.edit-btn');
            const storeId = btn.dataset.storeId;
            const storeNum = btn.dataset.storeNum;
            const storeName = btn.dataset.storeName;
            const storeEmail = btn.dataset.storeEmail;
            const storePhone = btn.dataset.storePhone;
            const storeSlots = btn.dataset.storeSlots;
            const contactName = btn.dataset.contactName;
            
            editStore(storeId, storeNum, storeName, storeEmail, storePhone, storeSlots, contactName);
        }
    });


    // Handle add returns button clicks
    document.addEventListener('click', function(e) {
        if (e.target.closest('.add-returns-btn')) {
            const btn = e.target.closest('.add-returns-btn');
            const storeNum = parseInt(btn.dataset.storeNum);
            const storeName = btn.dataset.storeName;
            openAddReturnsModal(storeNum, storeName);
        }
    });
    
    // Close modals when clicking outside
    document.getElementById('editModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeEditModal();
        }
    });

    document.getElementById('returnsModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeReturnsModal();
        }
    });

    document.getElementById('addReturnsModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeAddReturnsModal();
        }
    });

    document.getElementById('salesModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeSalesModal();
        }
    });

    // Handle edit form submission
    document.getElementById('editStoreForm').addEventListener('submit', function(e) {
        e.preventDefault();
        saveStoreChanges();
    });

    // Handle add returns form submission
    document.getElementById('addReturnsForm').addEventListener('submit', function(e) {
        e.preventDefault();
        saveReturnsEntry();
    });

    // Close modals with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (document.getElementById('editModal').classList.contains('active')) {
                closeEditModal();
            }
            if (document.getElementById('returnsModal').classList.contains('active')) {
                closeReturnsModal();
            }
            if (document.getElementById('salesModal').classList.contains('active')) {
                closeSalesModal();
            }
            if (document.getElementById('addReturnsModal').classList.contains('active')) {
                closeAddReturnsModal();
            }
        }
    });
});

// Returns Modal Functions
async function openReturnsModal() {
    document.getElementById('returnsModal').classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Load available years
    await loadReturnsYears();
}

function closeReturnsModal() {
    document.getElementById('returnsModal').classList.remove('active');
    document.body.style.overflow = '';
    currentSelectedYear = null;
}

async function loadReturnsYears() {
    try {
        const response = await fetch('/office/store-returns-years/');
        const data = await response.json();
        
        if (data.success && data.years.length > 0) {
            const yearFilter = document.getElementById('yearFilter');
            yearFilter.innerHTML = '';
            
            data.years.forEach(year => {
                const option = document.createElement('option');
                option.value = year;
                option.textContent = `20${year}`;
                yearFilter.appendChild(option);
            });
            
            // Load data for the first year
            currentSelectedYear = data.years[0];
            await loadReturnsData();
        } else {
            document.getElementById('yearFilter').innerHTML = '<option value="">No data available</option>';
            document.getElementById('returnsTableBody').innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 40px; color: #999;">
                        No returns data available. Add wholesale prices and returns to get started.
                    </td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('Error loading years:', error);
        showNotification('Error loading years', error.message, 'error');
    }
}

async function loadReturnsData() {
    const selectedYear = document.getElementById('yearFilter').value;
    if (!selectedYear) return;
    
    currentSelectedYear = selectedYear;
    
    // Show loading
    document.getElementById('returnsTableBody').innerHTML = `
        <tr>
            <td colspan="6" style="text-align: center; padding: 40px;">
                <div class="loading-spinner"></div>
                <p style="margin-top: 10px;">Loading data...</p>
            </td>
        </tr>
    `;
    
    try {
        const response = await fetch(`/office/store-returns-data/?year=${selectedYear}`);
        const data = await response.json();
        
        if (data.success) {
            returnsData = data.stores;
            renderReturnsTable(data.stores);
        } else {
            throw new Error(data.message || 'Failed to load returns data');
        }
    } catch (error) {
        console.error('Error loading returns data:', error);
        document.getElementById('returnsTableBody').innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 40px; color: #e74c3c;">
                    Error loading data: ${error.message}
                </td>
            </tr>
        `;
    }
}

function renderReturnsTable(stores) {
    const tbody = document.getElementById('returnsTableBody');
    
    if (stores.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 40px; color: #999;">
                    No stores found.
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = stores.map(store => `
        <tr>
            <td><strong>#${store.store_num}</strong></td>
            <td>${store.store_name}</td>
            <td>${store.packets_allowed}</td>
            <td>${store.packets_returned > 0 ? store.packets_returned : '--'}</td>
            <td class="credit-value">${store.credit > 0 ? '$' + store.credit.toFixed(2) : '$0.00'}</td>
            <td>
                <button class="add-btn add-returns-btn" 
                        data-store-num="${store.store_num}"
                        data-store-name="${store.store_name}"
                        title="Add/Edit returns for ${store.store_name}">
                    +
                </button>
            </td>
        </tr>
    `).join('');
    // tbody.innerHTML = stores.map(store => `
    //     <tr>
    //         <td><strong>#${store.store_num}</strong></td>
    //         <td>${store.store_name}</td>
    //         <td>${store.packets_allowed}</td>
    //         <td>${store.packets_returned > 0 ? store.packets_returned : '--'}</td>
    //         <td class="credit-value">${store.credit > 0 ? '$' + store.credit.toFixed(2) : '$0.00'}</td>
    //         <td>
    //             <button class="add-btn" 
    //                     onclick="openAddReturnsModal(${store.store_num}, '${store.store_name}')"
    //                     title="Add/Edit returns for ${store.store_name}">
    //                 +
    //             </button>
    //         </td>
    //     </tr>
    // `).join('');
}

// Add/Edit Returns Modal Functions
function openAddReturnsModal(storeNum, storeName) {
    // Find existing returns for this store
    const storeData = returnsData.find(s => s.store_num === storeNum);
    
    document.getElementById('addReturnsModalTitle').textContent = 
        `# pkts returned by ${storeName} for sales year ${currentSelectedYear}`;
    document.getElementById('addReturnsStoreName').value = storeName;
    document.getElementById('addReturnsStoreNum').value = storeNum;
    document.getElementById('addReturnsYear').value = `20${currentSelectedYear}`;
    document.getElementById('addReturnsPackets').value = storeData?.packets_returned || '';
    
    document.getElementById('addReturnsModal').classList.add('active');
}

function closeAddReturnsModal() {
    document.getElementById('addReturnsModal').classList.remove('active');
    document.getElementById('addReturnsForm').reset();
    clearErrors();
    hideSuccessMessage('addReturnsSuccessMessage');
}

async function saveReturnsEntry() {
    clearErrors();
    
    const storeNum = document.getElementById('addReturnsStoreNum').value;
    const packetsReturned = document.getElementById('addReturnsPackets').value;
    
    if (!packetsReturned || parseInt(packetsReturned) < 0) {
        showError('packets', 'Please enter a valid number of packets');
        return;
    }
    
    const formData = new FormData();
    formData.append('store_num', storeNum);
    formData.append('year', currentSelectedYear);
    formData.append('packets_returned', packetsReturned);
    
    try {
        const response = await fetch('/office/record-store-returns/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCSRFToken(),
            },
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccessMessage('addReturnsSuccessMessage');
            setTimeout(async () => {
                closeAddReturnsModal();
                await loadReturnsData(); // Reload the table
                showNotification('Returns Updated', 'Returns recorded successfully!', 'success');
            }, 1500);
        } else {
            if (data.errors) {
                for (const [field, errors] of Object.entries(data.errors)) {
                    showError(field, errors[0]);
                }
            } else {
                alert('Error recording returns: ' + (data.message || 'Unknown error'));
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error occurred. Please try again.');
    }
}


// Sales Modal Functions
async function openSalesModal() {
    document.getElementById('salesModal').classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Load available years
    await loadSalesYears();
}

function closeSalesModal() {
    document.getElementById('salesModal').classList.remove('active');
    document.body.style.overflow = '';
}

async function loadSalesYears() {
    try {
        // Use the same years endpoint as returns (gets years from StoreOrder)
        const response = await fetch('/office/store-returns-years/');
        const data = await response.json();
        
        if (data.success && data.years.length > 0) {
            const yearFilter = document.getElementById('salesYearFilter');
            yearFilter.innerHTML = '';
            
            data.years.forEach(year => {
                const option = document.createElement('option');
                option.value = year;
                option.textContent = `20${year}`;
                yearFilter.appendChild(option);
            });
            
            // Load data for the first year
            await loadSalesData();
        } else {
            document.getElementById('salesYearFilter').innerHTML = '<option value="">No data available</option>';
            document.getElementById('salesTableBody').innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 40px; color: #999;">
                        No sales data available.
                    </td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('Error loading years:', error);
        showNotification('Error', 'Failed to load years', 'error');
    }
}

async function loadSalesData() {
    const selectedYear = document.getElementById('salesYearFilter').value;
    if (!selectedYear) return;
    
    // Show loading
    document.getElementById('salesTableBody').innerHTML = `
        <tr>
            <td colspan="6" style="text-align: center; padding: 40px;">
                <div class="loading-spinner"></div>
                <p style="margin-top: 10px;">Loading data...</p>
            </td>
        </tr>
    `;
    
    try {
        const response = await fetch(`/office/store-sales-data/?year=${selectedYear}`);
        const data = await response.json();
        
        if (data.success) {
            renderSalesTable(data.stores);
        } else {
            throw new Error(data.message || 'Failed to load sales data');
        }
    } catch (error) {
        console.error('Error loading sales data:', error);
        document.getElementById('salesTableBody').innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 40px; color: #e74c3c;">
                    Error loading data: ${error.message}
                </td>
            </tr>
        `;
    }
}

function renderSalesTable(stores) {
    const tbody = document.getElementById('salesTableBody');
    
    if (stores.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 40px; color: #999;">
                    No stores found.
                </td>
            </tr>
        `;
        return;
    }
    
    // Calculate totals
    const grandTotalPackets = stores.reduce((sum, s) => sum + s.total_packets, 0);
    const grandSubtotal = stores.reduce((sum, s) => sum + s.subtotal, 0);
    const grandShipping = stores.reduce((sum, s) => sum + s.total_shipping, 0);
    const grandTotal = stores.reduce((sum, s) => sum + s.total, 0);
    
    tbody.innerHTML = stores.map(store => `
        <tr>
            <td><strong>#${store.store_num}</strong></td>
            <td>${store.store_name}</td>
            <td style="text-align: right;">${store.total_packets}</td>
            <td style="text-align: right;" class="money-value">$${store.subtotal.toFixed(2)}</td>
            <td style="text-align: right;" class="money-value">$${store.total_shipping.toFixed(2)}</td>
            <td style="text-align: right;" class="total-value">$${store.total.toFixed(2)}</td>
        </tr>
    `).join('') + `
        <tr style="border-top: 3px solid #e67e22; background: rgba(243, 156, 18, 0.05);">
            <td colspan="2" style="text-align: right; font-weight: 700; padding: 15px;"><strong>TOTALS:</strong></td>
            <td style="text-align: right; font-weight: 700;">${grandTotalPackets}</td>
            <td style="text-align: right; font-weight: 700; color: #f39c12;">$${grandSubtotal.toFixed(2)}</td>
            <td style="text-align: right; font-weight: 700; color: #f39c12;">$${grandShipping.toFixed(2)}</td>
            <td style="text-align: right; font-weight: 700; color: #e67e22; font-size: 1.1rem;">$${grandTotal.toFixed(2)}</td>
        </tr>
    `;
}


// Edit Store Functions
function editStore(storeId, storeNum, storeName, storeEmail, storePhone, storeSlots, contactName) {
    currentStoreId = storeNum;
    currentStoreNum = storeNum;
    
    document.getElementById('storeName').value = storeName || '';
    document.getElementById('contactEmail').value = storeEmail || '';
    document.getElementById('contactPhone').value = storePhone || '';
    document.getElementById('storeSlots').value = storeSlots || '';
    document.getElementById('contactName').value = contactName || '';
    
    document.getElementById('editModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    document.body.style.overflow = '';
    currentStoreId = null;
    currentStoreNum = null;
}

function saveStoreChanges() {
    const storeIdentifier = currentStoreNum || currentStoreId;
    
    const formData = {
        store_num: storeIdentifier,
        name: document.getElementById('storeName').value,
        contact_name: document.getElementById('contactName').value,
        contact_phone: document.getElementById('contactPhone').value,
        email: document.getElementById('contactEmail').value,
        address: document.getElementById('storeAddress').value,
        city: document.getElementById('storeCity').value,
        state: document.getElementById('storeState').value,
        zip: document.getElementById('storeZip').value,
        slots: document.getElementById('storeSlots').value,
        rack_num: document.getElementById('rackNum').value,
        header: document.getElementById('header').value,
        rack_material: document.getElementById('rackMaterial').value,
        velcro: document.getElementById('velcro').checked,
        first_order: document.getElementById('firstOrder').value
    };

    const storeNum = parseInt(storeIdentifier);
    const updateUrl = `/office/${storeNum}/update/`;

    fetch(updateUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify(formData)
    })
    .then(response => {
        if (response.status === 500) {
            return response.text().then(text => {
                throw new Error(`Server error (500): Check Django logs for details`);
            });
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    })
    .then(data => {
        if (data.success) {
            updateTableRow(formData);
            closeEditModal();
            showNotification('Store Updated', 'Store updated successfully!', 'success');
        } else {
            console.error('Server returned error:', data.error);
            alert('Error saving changes: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Full error object:', error);
        alert('An error occurred while saving changes: ' + error.message);
    });
}

function updateTableRow(data) {
    const storeIdentifier = currentStoreNum || currentStoreId;
    const rows = document.querySelectorAll('.stores-table tbody tr');
    
    rows.forEach((row) => {
        const editBtn = row.querySelector('.edit-btn');
        if (editBtn && editBtn.dataset.storeNum === String(storeIdentifier)) {
            const cells = row.querySelectorAll('td');
            
            const storeNameCell = cells[1]?.querySelector('.store-name');
            if (storeNameCell) {
                storeNameCell.textContent = data.name || 'Unnamed Store';
            }
            
            const contactCells = row.querySelectorAll('td.col-group-contact');
            if (contactCells[0] && data.contact_name) contactCells[0].textContent = data.contact_name;
            if (contactCells[1] && data.contact_phone) {
                contactCells[1].innerHTML = `<span class="phone-number">${data.contact_phone}</span>`;
            }
            if (contactCells[2] && data.email) {
                contactCells[2].innerHTML = `<a href="mailto:${data.email}" class="email-link">${data.email}</a>`;
            }
            if (contactCells[3] && data.address) contactCells[3].textContent = data.address;
            if (contactCells[4] && data.city) contactCells[4].textContent = data.city;
            if (contactCells[5] && data.state) contactCells[5].textContent = data.state;
            if (contactCells[6] && data.zip) contactCells[6].textContent = data.zip;
            
            const rackCells = row.querySelectorAll('td.col-group-rack');
            if (rackCells[0] && data.slots) {
                rackCells[0].innerHTML = `<strong>${data.slots}</strong>`;
            }
            if (rackCells[1] && data.header) rackCells[1].textContent = data.header;
            if (rackCells[2]) {
                const velcroClass = data.velcro ? 'boolean-true' : 'boolean-false';
                const velcroSymbol = data.velcro ? '✓' : '✗';
                rackCells[2].innerHTML = `<span class="boolean-indicator ${velcroClass}">${velcroSymbol}</span>`;
            }
            if (rackCells[3] && data.rack_material) rackCells[3].textContent = data.rack_material;
            if (rackCells[4] && data.rack_num) rackCells[4].textContent = data.rack_num;
            
            const orderCell = row.querySelector('td.col-group-order');
            if (orderCell && data.first_order) {
                orderCell.textContent = data.first_order;
            }

            editBtn.dataset.storeId = String(storeIdentifier);
            editBtn.dataset.storeNum = String(storeIdentifier);
            editBtn.dataset.storeName = data.name || '';
            editBtn.dataset.storeEmail = data.email || '';
            editBtn.dataset.storePhone = data.contact_phone || '';
            editBtn.dataset.storeSlots = data.slots || '';
            editBtn.dataset.contactName = data.contact_name || '';
            
            return;
        }
    });
}

// Utility Functions
function clearErrors() {
    const errorElements = document.querySelectorAll('.error-message');
    errorElements.forEach(element => {
        element.style.display = 'none';
        element.textContent = '';
    });
}

function showError(fieldName, message) {
    const errorElement = document.getElementById(fieldName + '_error');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
}

function showSuccessMessage(elementId) {
    const successElement = document.getElementById(elementId);
    if (successElement) {
        successElement.style.display = 'block';
        setTimeout(() => {
            successElement.style.display = 'none';
        }, 3000);
    }
}

function hideSuccessMessage(elementId) {
    const successElement = document.getElementById(elementId);
    if (successElement) {
        successElement.style.display = 'none';
    }
}


function showNotification(title, message, type = 'success') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 12px;
        color: white;
        font-weight: 600;
        z-index: 9999;
        animation: slideInRight 0.3s ease-out;
        background: ${type === 'success' ? 'linear-gradient(135deg, #10ac84, #01a3a4)' : 'linear-gradient(135deg, #ee5a24, #ff6b6b)'};
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
    `;
    notification.innerHTML = `<strong>${title}</strong><br>${message}`;
    
    document.body.appendChild(notification);
    
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from {
                opacity: 0;
                transform: translateX(100px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        @keyframes slideOutRight {
            from {
                opacity: 1;
                transform: translateX(0);
            }
            to {
                opacity: 0;
                transform: translateX(100px);
            }
        }
    `;
    document.head.appendChild(style);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-in';
        setTimeout(() => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
            if (document.head.contains(style)) {
                document.head.removeChild(style);
            }
        }, 300);
    }, 3000);
}