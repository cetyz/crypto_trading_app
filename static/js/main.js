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

    // Configure marked options
    marked.setOptions({
        breaks: true, // Interpret line breaks as <br>
        gfm: true,    // Use GitHub Flavored Markdown
    });

    let currentMessageBuffer = '';
    let currentMessageElement = null;

    function startNewMessage(sender) {
        currentMessageBuffer = '';
        currentMessageElement = document.createElement('div');
        currentMessageElement.innerHTML = `<strong>${sender}:</strong> <span class="message-content"></span>`;
        chatMessages.appendChild(currentMessageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    function appendToMessage(content) {
        currentMessageBuffer += content;
        currentMessageElement.querySelector('.message-content').innerHTML = currentMessageBuffer.replace(/\n/g, '<br>');
    }
    
    function finalizeMessage() {
        const parsedContent = parseAndSanitizeMarkdown(currentMessageBuffer);
        currentMessageElement.querySelector('.message-content').innerHTML = parsedContent;
        currentMessageBuffer = '';
        currentMessageElement = null;
    }

    function parseAndSanitizeMarkdown(content) {
        // Ensure there's a line break before headers if not already present
        content = content.replace(/(?<!\n)^(#{1,6}\s)/gm, '\n$1');
        
        const rawHtml = marked.parse(content, {
            breaks: true,
            gfm: true,
            headerIds: false // Disable automatic ID generation for headers
        });
        return DOMPurify.sanitize(rawHtml, {
            ALLOW_UNKNOWN_PROTOCOLS: true,
            ADD_ATTR: ['target'],
            FORBID_TAGS: ['style', 'script'],
            FORBID_ATTR: ['style']
        });
    }

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
        startNewMessage(sender);
        appendToMessage(message);
        finalizeMessage();
    }

    // Send message to the server and handle the streaming response
    function sendMessage(message) {
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
            
            startNewMessage('AI');  // Start a new AI message
    
            function readStream() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        finalizeMessage();  // Finalize the message when the stream is done
                        return;
                    }
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');
                    lines.forEach(line => {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') {
                                finalizeMessage();  // Finalize the message when '[DONE]' is received
                            } else {
                                appendToMessage(data);  // Append each chunk of data
                            }
                        }
                    });
                    readStream();  // Continue reading the stream
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
            const strategyJson = JSON.parse(data.strategy_json);
            let strategyName = strategyJson.strategy_name;
            
            // Function to check if a strategy name already exists
            function strategyNameExists(name) {
                return fetch('/check_strategy_name', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name }),
                })
                .then(response => response.json())
                .then(result => result.exists);
            }
    
            // Function to get a unique strategy name
            function getUniqueStrategyName(baseName) {
                let nameCounter = 1;
                let currentName = baseName;
                
                return new Promise((resolve) => {
                    function checkName() {
                        strategyNameExists(currentName).then(exists => {
                            if (!exists) {
                                resolve(currentName);
                            } else {
                                currentName = `${baseName} (${nameCounter})`;
                                nameCounter++;
                                checkName();
                            }
                        });
                    }
                    checkName();
                });
            }
    
            // Get a unique strategy name and then save the strategy
            getUniqueStrategyName(strategyName).then(uniqueName => {
                const newStrategy = {
                    name: uniqueName,
                    summary: data.strategy_summary,
                    json: data.strategy_json
                };
    
                return fetch('/save_strategy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newStrategy),
                });
            })
            .then(response => response.json())
            .then(result => {
                updateStrategySelector(result.strategies);
                strategySelector.value = result.strategies[result.strategies.length - 1].name;
                displayStrategy(result.strategies[result.strategies.length - 1]);
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
        strategyDisplay.innerHTML = parseAndSanitizeMarkdown(strategy.summary);
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

    // Initialize chat functionality
    initializeChat();
});

function initializeChat() {
    // Your chat initialization code here
    // For example, attaching event listeners to the chat form
    document.getElementById('chat-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const message = document.getElementById('chat-input').value;
        if (message.trim()) {
            addMessage('User', message);
            // Send message to backend, etc.
        }
    });
}