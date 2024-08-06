document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const chatForm = document.getElementById('chat-form');

    // Function to adjust textarea height
    function adjustTextareaHeight() {
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
    }

    // Event listener for input to adjust height
    chatInput.addEventListener('input', adjustTextareaHeight);

    // Event listener for keydown to handle Enter and Shift+Enter
    chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            if (e.shiftKey) {
                // Shift+Enter: add a new line
                return;
            } else {
                // Enter without shift: submit the form
                e.preventDefault();
                chatForm.dispatchEvent(new Event('submit'));
            }
        }
    });

    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (message) {
            addMessage('User', message);
            chatInput.value = '';
            adjustTextareaHeight(); // Reset height after sending
            sendMessage(message);
        }
    });

    function addMessage(sender, message) {
        const messageElement = document.createElement('div');
        messageElement.innerHTML = `<strong>${sender}:</strong> ${message.replace(/\n/g, '<br>')}`;
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function sendMessage(message) {
        addMessage('AI', ''); // Add an empty message for the AI's response
        const aiMessageElement = chatMessages.lastElementChild;

        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({message: message}),
        })
        .then(response => {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            function readStream() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        return;
                    }
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');
                    lines.forEach(line => {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') {
                                return;
                            }
                            aiMessageElement.innerHTML += data;
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        }
                    });
                    readStream();
                });
            }
            
            readStream();
        })
        .catch((error) => {
            console.error('Error:', error);
            addMessage('System', 'An error occurred while processing your request.');
        });
    }

    // Initial call to set correct height
    adjustTextareaHeight();
});