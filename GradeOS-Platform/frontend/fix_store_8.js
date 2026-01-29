const fs = require('fs');
const path = require('path');

const filePath = path.join(process.cwd(), 'src/store/consoleStore.ts');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

const newLines = lines.map(line => {
    // Fix type error in agent_update handler
    if (line.includes('const label = data.agentLabel') && !line.includes('as any')) {
        return line.replace('data.agentLabel', '(data as any).agentLabel')
            .replace('data.agent_label', '(data as any).agent_label')
            .replace('data.agentName', '(data as any).agentName')
            .replace('data.agent_name', '(data as any).agent_name');
    }
    // Fix parentNodeId type error too if similar
    if (line.includes('const parentNodeId = data.parentNodeId')) {
        return line.replace('data.parentNodeId', '(data as any).parentNodeId')
            .replace('data.nodeId', '(data as any).nodeId');
    }
    return line;
});

fs.writeFileSync(filePath, newLines.join('\n'), 'utf8');
console.log('Fixed consoleStore.ts part 8');
