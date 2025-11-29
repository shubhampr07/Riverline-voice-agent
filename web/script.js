// Configuration
const API_BASE_URL = 'http://localhost:5000'; // You'll need to create a simple API server

// State
let callHistory = [];

// DOM Elements
const callForm = document.getElementById('callForm');
const callButton = document.getElementById('callButton');
const callHistoryContainer = document.getElementById('callHistory');
const refreshButton = document.getElementById('refreshButton');
const toast = document.getElementById('toast');

// Load environment variables (in production, these should come from your backend)
const LIVEKIT_URL = 'wss://riverline-agent-l4hwapa5.livekit.cloud';
const TRUNK_ID = 'ST_RjVXok8tne5Z';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set default trunk ID
    document.getElementById('trunkId').value = TRUNK_ID;
    
    // Set default due date to today
    document.getElementById('dueDate').valueAsDate = new Date();
    
    // Load call history from localStorage
    loadCallHistory();
    
    // Event listeners
    callForm.addEventListener('submit', handleCallSubmit);
    refreshButton.addEventListener('click', loadCallHistory);
});

// Handle form submission
async function handleCallSubmit(e) {
    e.preventDefault();
    
    const formData = {
        phone_number: document.getElementById('phoneNumber').value,
        customer_name: document.getElementById('customerName').value,
        amount_due: document.getElementById('amountDue').value,
        due_date: document.getElementById('dueDate').value,
        trunk_id: document.getElementById('trunkId').value || TRUNK_ID,
        summary: document.getElementById('summary').value || 'No previous conversation'
    };
    
    // Validate phone number format
    if (!formData.phone_number.match(/^\+[1-9]\d{1,14}$/)) {
        showToast('Please enter a valid phone number in E.164 format (e.g., +19892822468)', 'error');
        return;
    }
    
    // Disable button and show loading
    callButton.disabled = true;
    callButton.classList.add('loading');
    callButton.querySelector('span').textContent = 'Initiating...';
    
    try {
        // Call the LiveKit dispatch API
        await initiateCall(formData);
        
        // Add to call history
        const callRecord = {
            id: Date.now(),
            phone: formData.phone_number,
            customer: formData.customer_name,
            amount: formData.amount_due,
            status: 'pending',
            timestamp: new Date().toISOString()
        };
        
        callHistory.unshift(callRecord);
        saveCallHistory();
        renderCallHistory();
        
        showToast('Call initiated successfully!', 'success');
        
        // Reset form
        callForm.reset();
        document.getElementById('trunkId').value = TRUNK_ID;
        document.getElementById('dueDate').valueAsDate = new Date();
        
    } catch (error) {
        console.error('Error initiating call:', error);
        showToast('Failed to initiate call: ' + error.message, 'error');
    } finally {
        // Re-enable button
        callButton.disabled = false;
        callButton.classList.remove('loading');
        callButton.querySelector('span').textContent = 'Initiate Call';
    }
}

// Initiate call using LiveKit dispatch
async function initiateCall(formData) {
    const metadata = {
        phone_number: formData.phone_number,
        trunk_id: formData.trunk_id,
        customer_name: formData.customer_name,
        amount_due: formData.amount_due,
        due_date: formData.due_date,
        summary: formData.summary
    };
    
    // Call the Flask backend API
    const response = await fetch(`${API_BASE_URL}/api/initiate-call`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(metadata)
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to initiate call');
    }
    
    return await response.json();
}

// Render call history
function renderCallHistory() {
    if (callHistory.length === 0) {
        callHistoryContainer.innerHTML = `
            <div class="empty-state">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" opacity="0.3">
                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                </svg>
                <p>No calls initiated yet</p>
                <small>Start by initiating a call above</small>
            </div>
        `;
        return;
    }
    
    callHistoryContainer.innerHTML = callHistory.map(call => `
        <div class="call-item">
            <div class="call-item-header">
                <div class="call-item-phone">${call.phone}</div>
                <div class="call-item-status status-${call.status}">
                    ${call.status.toUpperCase()}
                </div>
            </div>
            <div class="call-item-details">
                ${call.customer} • $${call.amount}
            </div>
            <div class="call-item-time">
                ${formatTimestamp(call.timestamp)}
            </div>
        </div>
    `).join('');
}

// Format timestamp
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) {
        return 'Just now';
    } else if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    } else if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else {
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
}

// Show toast notification
function showToast(message, type = 'success') {
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Save call history to localStorage
function saveCallHistory() {
    localStorage.setItem('callHistory', JSON.stringify(callHistory));
}

// Load call history from localStorage
function loadCallHistory() {
    const saved = localStorage.getItem('callHistory');
    if (saved) {
        callHistory = JSON.parse(saved);
        renderCallHistory();
    }
}

// Simulate status updates
setInterval(() => {
    let updated = false;
    callHistory = callHistory.map(call => {
        if (call.status === 'pending') {
            const random = Math.random();
            if (random > 0.7) {
                updated = true;
                return { ...call, status: 'success' };
            } else if (random < 0.1) {
                updated = true;
                return { ...call, status: 'failed' };
            }
        }
        return call;
    });
    
    if (updated) {
        saveCallHistory();
        renderCallHistory();
    }
}, 5000);
