document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const chatForm = document.getElementById('chat-form');
    const clearMemoryButton = document.getElementById('clear-memory');

    /// Function to dynamically adjust textarea height based on content
    function adjustTextareaHeight() {
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
    }

    // Adjust textarea height as user types
    chatInput.addEventListener('input', adjustTextareaHeight);

    // Handle Enter and Shift+Enter key presses
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

    // Handle form submission
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

    // Add a message to the chat interface
    function addMessage(sender, message) {
        const messageElement = document.createElement('div');
        // Replace newlines with <br> tags for proper display
        messageElement.innerHTML = `<strong>${sender}:</strong> ${message.replace(/\n/g, '<br>')}`;
        chatMessages.appendChild(messageElement);
        // Scroll to the bottom of the chat
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Send message to the server and handle the streaming response
    function sendMessage(message) {
        // Add an empty message for the AI's response
        addMessage('AI', '');
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
            
            // Function to recursively read the stream
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
                            // Append the received data to the AI's message
                            aiMessageElement.innerHTML += data;
                            // Scroll to the bottom as new content arrives
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        }
                    });
                    // Continue reading the stream
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

    // Handle clearing of chat memory
    clearMemoryButton.addEventListener('click', function() {
        fetch('/clear_memory', {
            method: 'POST',
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
            // Clear the chat messages on the frontend
            chatMessages.innerHTML = '';
            addMessage('System', 'Memory has been cleared. You can start a new conversation.');
        })
        .catch((error) => {
            console.error('Error:', error);
            addMessage('System', 'An error occurred while clearing the memory.');
        });
    });

    // Initialize the textarea height
    adjustTextareaHeight();
});