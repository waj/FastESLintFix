const eslint = require('eslint');
const http = require('http');
const cli = new eslint.CLIEngine();

const server = http.createServer((req, res) => {
  var body = [];
  req.on('data', (buf) => { body.push(buf) });
  req.on('end', () => {
    const content = Buffer.concat(body).toString();
    var report = cli.executeOnText(content);
    res.end(JSON.stringify(report.results[0].messages));
  })
})

server.on('listening', () => {
  console.log(server.address().port)
})

server.listen();
