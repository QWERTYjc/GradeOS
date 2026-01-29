const fs = require('fs');
const path = require('path');

const filePath = path.join(process.cwd(), 'src/store/consoleStore.ts');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

const newLines = lines.map(line => {
    // Fix line 1689: malformed string in fetch body
    if (line.includes('ingest/58ab5b36-845e-4544-9ec4-a0b6e7a57748') && line.includes('headers')) {
        // Comment out the debug fetch or fix it.
        // Fixing it requires guessing the intent. It seems like a debug log.
        // The safest is to comment it out to unblock build, or reconstruct it validly.
        // I will commented it out.
        return `        // Debug fetch commented out due to syntax error
        // fetch('http://127.0.0.1:7242/ingest/58ab5b36-845e-4544-9ec4-a0b6e7a57748', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'consoleStore.ts:setFinalResults', message: 'Set Final Results', data: { count: formattedResults.length }, timestamp: Date.now() }) }).catch(() => {});`;
    }
    return line;
});

fs.writeFileSync(filePath, newLines.join('\n'), 'utf8');
console.log('Fixed consoleStore.ts part 3');
