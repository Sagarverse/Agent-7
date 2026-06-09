// Agent-7 Dashboard Controller
document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const statusBadge = document.getElementById('statusBadge');
    const statusText = statusBadge.querySelector('.status-text');
    const actionCountEl = document.getElementById('actionCount');
    const taskCountEl = document.getElementById('taskCount');
    const btnScreenshot = document.getElementById('btnScreenshot');
    const btnClearLog = document.getElementById('btnClearLog');
    const screenContainer = document.getElementById('screenContainer');
    const screenImage = document.getElementById('screenImage');
    const screenTimestamp = document.getElementById('screenTimestamp');
    const currentTaskContainer = document.getElementById('currentTask');
    const actionLog = document.getElementById('actionLog');

    let socket = null;
    let actionsCount = 0;
    let tasksCount = 0;

    // Connect WebSocket
    function connectSocket() {
        updateStatusBadge('connecting', 'Connecting...');
        
        socket = io({
            reconnectionAttempts: 5,
            timeout: 5000
        });

        socket.on('connect', () => {
            console.log('Connected to Agent-7 server');
            updateStatusBadge('idle', 'Idle');
            fetchInitialStatus();
            fetchScreenshot();
        });

        socket.on('disconnect', () => {
            console.warn('Disconnected from server');
            updateStatusBadge('connecting', 'Offline');
        });

        socket.on('status_update', (data) => {
            console.log('Status Update:', data);
            addLogEntry('system', data.message, data.timestamp);
            
            // Check if status is a task planning or completion status
            if (data.message.includes('Planning task...')) {
                updateStatusBadge('running', 'Running');
            } else if (data.message.includes('Task completed') || data.message.includes('Task aborted') || data.message.includes('Error:')) {
                updateStatusBadge('idle', 'Idle');
                fetchInitialStatus();
            }
        });

        socket.on('action_update', (data) => {
            console.log('Action Update:', data);
            const action = data.action;
            const type = action.action || 'system';
            const desc = action.thinking ? `[Reasoning] ${action.thinking} \n↳ [Action] ${action.message || descForAction(action)}` : (action.description || 'Action executed');
            
            addLogEntry(type, desc, data.timestamp);
            actionsCount++;
            actionCountEl.textContent = actionsCount;
            
            // Auto update screenshot on new action
            setTimeout(fetchScreenshot, 500);
        });
    }

    function descForAction(action) {
        if (!action.action) return 'Unknown Action';
        let desc = action.action;
        if (action.params) {
            desc += `: ${JSON.stringify(action.params)}`;
        }
        return desc;
    }

    let screenshotInterval = null;

    function startScreenshotInterval() {
        if (!screenshotInterval) {
            screenshotInterval = setInterval(fetchScreenshot, 2500);
        }
    }

    function stopScreenshotInterval() {
        if (screenshotInterval) {
            clearInterval(screenshotInterval);
            screenshotInterval = null;
        }
    }

    // Update the status badge appearance
    function updateStatusBadge(status, text) {
        statusBadge.className = 'status-badge ' + status;
        statusText.textContent = text;
        if (status === 'running') {
            startScreenshotInterval();
        } else {
            stopScreenshotInterval();
        }
    }

    // Fetch initial state via REST API
    async function fetchInitialStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            
            if (data.status === 'running') {
                updateStatusBadge('running', 'Running');
            } else if (data.status === 'idle') {
                updateStatusBadge('idle', 'Idle');
            }

            if (data.recent_actions && data.recent_actions.length > 0) {
                // Clear initial placeholder log entries if we have actual logs
                if (actionLog.querySelector('.log-time').textContent === '--:--') {
                    actionLog.innerHTML = '';
                }
                
                // Clear counters and rebuild
                actionsCount = data.recent_actions.length;
                actionCountEl.textContent = actionsCount;
                
                // Sort actions chronologically
                data.recent_actions.forEach(act => {
                    addLogEntry(act.action_type, act.description, act.timestamp);
                });
            }
            
            // Get task count
            if (data.task_summary) {
                const lines = data.task_summary.split('\n');
                // The task summary lists tasks with bullet points
                const count = (data.task_summary.match(/^[ 	]*[✅❌⏳]/gm) || []).length;
                tasksCount = count;
                taskCountEl.textContent = tasksCount;
                
                // Update current task display
                const runningTaskLine = lines.find(l => l.includes('⏳'));
                if (runningTaskLine) {
                    currentTaskContainer.innerHTML = `
                        <div class="task-info">
                            <p class="task-command">⚡ Running: ${runningTaskLine.replace(/^[ 	]*⏳[ 	]*/, '')}</p>
                        </div>
                    `;
                } else {
                    currentTaskContainer.innerHTML = '<p class="task-idle">No active task</p>';
                }
            }
        } catch (err) {
            console.error('Error fetching status:', err);
        }
    }

    // Fetch Screenshot
    async function fetchScreenshot() {
        try {
            const res = await fetch('/api/screenshot');
            const data = await res.json();
            
            if (data.screenshot) {
                const placeholder = screenContainer.querySelector('.screen-placeholder');
                if (placeholder) placeholder.style.display = 'none';
                
                screenImage.src = `data:image/png;base64,${data.screenshot}`;
                screenImage.style.display = 'block';
                
                const time = new Date(data.timestamp);
                screenTimestamp.textContent = time.toLocaleTimeString();
            }
        } catch (err) {
            console.error('Error fetching screenshot:', err);
        }
    }

    // Append entry to action log
    function addLogEntry(type, message, timestampStr) {
        const time = timestampStr ? new Date(timestampStr) : new Date();
        const formattedTime = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;
        
        // Add specific class mapping if needed
        if (type.startsWith('browser_')) {
            entry.classList.add('log-click');
        }
        
        entry.innerHTML = `
            <span class="log-time">${formattedTime}</span>
            <span class="log-message">${escapeHtml(message)}</span>
        `;
        
        // Scroll to bottom
        actionLog.appendChild(entry);
        actionLog.scrollTop = actionLog.scrollHeight;
    }

    function escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Event Listeners
    btnScreenshot.addEventListener('click', () => {
        fetchScreenshot();
    });

    btnClearLog.addEventListener('click', () => {
        actionLog.innerHTML = `
            <div class="log-entry log-system">
                <span class="log-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                <span class="log-message">Log cleared.</span>
            </div>
        `;
        actionsCount = 0;
        actionCountEl.textContent = '0';
    });

    // Run connection
    connectSocket();
});
