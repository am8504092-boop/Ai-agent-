document.addEventListener('DOMContentLoaded', () => {
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const chatBox = document.getElementById('chat-box');
    const screenshotImg = document.getElementById('screenshot');
    const browserView = document.getElementById('browser-view');

    messageForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const command = messageInput.value.trim();
        if (!command) return;

        appendMessage(command, 'user');
        messageInput.value = '';
        showLoading();

        try {
            const response = await fetch('/api/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ command: command }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            appendMessage(data.reply, 'assistant');

            // Update screenshot with a cache-busting query parameter
            screenshotImg.src = data.screenshot_path + '?t=' + new Date().getTime();

        } catch (error) {
            console.error('Error:', error);
            appendMessage('عفواً، حدث خطأ أثناء معالجة طلبك.', 'assistant');
        } finally {
            hideLoading();
        }
    });

    function appendMessage(text, type) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', type);

        const p = document.createElement('p');
        p.textContent = text;
        messageDiv.appendChild(p);

        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function showLoading() {
        // Add a loading indicator to the chat
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-indicator';
        loadingDiv.classList.add('message', 'assistant');
        loadingDiv.innerHTML = `<p>يفكر...</p>`;
        chatBox.appendChild(loadingDiv);
        chatBox.scrollTop = chatBox.scrollHeight;

        // Add a loading overlay on the browser view
        const overlay = document.createElement('div');
        overlay.id = 'browser-loading-overlay';
        overlay.style.position = 'absolute';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.zIndex = '10';
        overlay.innerHTML = '<h3>...جاري التنفيذ</h3>';
        browserView.style.position = 'relative';
        browserView.appendChild(overlay);
    }

    function hideLoading() {
        const loadingIndicator = document.getElementById('loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
        const overlay = document.getElementById('browser-loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }
});
