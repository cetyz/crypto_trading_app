document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const chatForm = document.getElementById('chat-form');
    const clearMemoryButton = document.getElementById('clear-memory');
    const instrumentSelect = document.getElementById('instrument-select');
    const timeframeSelect = document.getElementById('timeframe-select');
    const createStrategyButton = document.getElementById('create-strategy-button');
    const strategyDisplay = document.getElementById('strategy-display');
    const jsonDisplay = document.getElementById('json-display');
    const strategySelector = document.getElementById('strategy-selector');
    const deleteStrategyButton = document.getElementById('delete-strategy-button');

    let strategies = [];

    function updateBacktestingParameters() {
        const instrument = instrumentSelect.value;
        const timeframe = timeframeSelect.value;
        
        fetch('/set_backtest_params', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({instrument: instrument, timeframe: timeframe}),
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
            // You can add more logic here, like updating UI elements
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    }

    instrumentSelect.addEventListener('change', updateBacktestingParameters);
    timeframeSelect.addEventListener('change', updateBacktestingParameters);

    // Initial call to set up any necessary state
    updateBacktestingParameters();


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

    createStrategyButton.addEventListener('click', function() {
        const chatHistory = Array.from(chatMessages.children).map(msg => msg.textContent).join('\n');

        fetch('/generate_strategy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({chat_history: chatHistory}),
        })
        .then(response => response.json())
        .then(data => {
            const newStrategy = {
                name: `Strategy ${Date.now()}`,  // Use timestamp for unique names
                summary: data.strategy_summary,
                json: data.strategy_json
            };

            fetch('/save_strategy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newStrategy),
            })
            .then(response => response.json())
            .then(result => {
                updateStrategySelector(result.strategies);
                strategySelector.value = newStrategy.name;
                displayStrategy(newStrategy);
            })
            .catch(error => console.error('Error saving strategy:', error));
        })
        .catch(error => console.error('Error generating strategy:', error));
    });

    function loadStrategies() {
        fetch('/get_strategies')
            .then(response => response.json())
            .then(strategies => {
                updateStrategySelector(strategies);
                if (strategies.length > 0) {
                    strategySelector.value = strategies[0].name;
                    displayStrategy(strategies[0]);
                }
            })
            .catch(error => console.error('Error loading strategies:', error));
    }

    function updateStrategySelector(strategies) {
        strategySelector.innerHTML = '';
        strategies.forEach(strategy => {
            const option = document.createElement('option');
            option.value = strategy.name;
            option.textContent = strategy.name;
            strategySelector.appendChild(option);
        });
    }

    function displayStrategy(strategy) {
        strategyDisplay.textContent = strategy.summary;
        jsonDisplay.textContent = JSON.stringify(JSON.parse(strategy.json), null, 2);
    }

    strategySelector.addEventListener('change', function() {
        fetch('/get_strategies')
            .then(response => response.json())
            .then(strategies => {
                const selectedStrategy = strategies.find(s => s.name === this.value);
                if (selectedStrategy) {
                    displayStrategy(selectedStrategy);
                }
            })
            .catch(error => console.error('Error loading strategies:', error));
    });

    deleteStrategyButton.addEventListener('click', function() {
        const selectedStrategyName = strategySelector.value;
        if (selectedStrategyName) {
            fetch('/delete_strategy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({name: selectedStrategyName}),
            })
            .then(response => response.json())
            .then(result => {
                updateStrategySelector(result.strategies);
                if (result.strategies.length > 0) {
                    strategySelector.value = result.strategies[0].name;
                    displayStrategy(result.strategies[0]);
                } else {
                    strategyDisplay.textContent = '';
                    jsonDisplay.textContent = '';
                }
            })
            .catch(error => console.error('Error deleting strategy:', error));
        }
    });

    // Load strategies when the page loads
    loadStrategies();

    // Initialize the textarea height
    adjustTextareaHeight();
});