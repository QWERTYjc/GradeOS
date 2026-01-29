const fs = require('fs');
const path = require('path');

const filePath = path.join(process.cwd(), 'src/store/consoleStore.ts');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

let stack = [];
let connectWsStarted = false;
let connectWsLine = -1;

for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (line.includes('connectWs: (batchId) => {')) {
        connectWsStarted = true;
        connectWsLine = i + 1;
        stack.push('{'); // Start of function body
        console.log(`connectWs started at line ${i + 1}`);
        continue;
    }

    if (!connectWsStarted) continue;

    for (let char of line) {
        if (char === '{') stack.push('{');
        else if (char === '}') {
            if (stack.length === 0) {
                console.log(`ERROR: Extra closing brace at line ${i + 1}`);
                process.exit(1);
            }
            stack.pop();
            // If stack is empty now, connectWs closed
            if (stack.length === 0) {
                console.log(`connectWs closed at line ${i + 1}`);
                // Peek next lines to see if we have code outside
                // We will continue loop to see if we find wsClient.on usage outside
            }
        }
    }

    if (stack.length === 0 && connectWsStarted) {
        // Check if we have wsClient calls after close
        if (line.includes('wsClient.on')) {
            console.log(`Found wsClient.on OUTSIDE connectWs at line ${i + 1}`);
        }
    }
}

if (stack.length > 0) {
    console.log(`connectWs never closed. Stack depth: ${stack.length}`);
}
