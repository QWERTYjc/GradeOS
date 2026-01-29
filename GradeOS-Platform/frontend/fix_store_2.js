const fs = require('fs');
const path = require('path');

const filePath = path.join(process.cwd(), 'src/store/consoleStore.ts');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

let fixedCount = 0;
const newLines = lines.map(line => {
    // Fix line 1052: merged closing brace into comment
    if (line.includes('return state;') && line.includes('//') && (line.includes('}') || line.includes('?'))) {
        // We look for the pattern "return state; // ... }" or similar
        // Since we know the intent is to close the if, we simply replace the line structure
        // assuming indentation
        return `                return state; // KEEPALIVE
            }`;
    }
    return line;
});

fs.writeFileSync(filePath, newLines.join('\n'), 'utf8');
console.log('Fixed consoleStore.ts part 2');
