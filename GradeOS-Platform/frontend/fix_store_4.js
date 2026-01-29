const fs = require('fs');
const path = require('path');

const filePath = path.join(process.cwd(), 'src/store/consoleStore.ts');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

const newLines = lines.map(line => {
    // Check for the fetch URL line
    if (line.includes('ingest/58ab5b36-845e-4544-9ec4-a0b6e7a57748')) {
        return '// ' + line;
    }
    // Check for the body line with the malformed string
    if (line.includes('consoleStore.ts:setFinalResults') && line.includes('message:')) {
        return '// ' + line;
    }
    return line;
});

fs.writeFileSync(filePath, newLines.join('\n'), 'utf8');
console.log('Fixed consoleStore.ts part 4');
