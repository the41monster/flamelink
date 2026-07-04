const express = require('express');
const { fib } = require('./utils');

const app = express();
const port = 3000;

app.get('/fib', (req, res) => {
    let n = req.query.n;
    if (!n || isNaN(n)){
        return res.status(400).send('Please provide a valid number n as a query parameter.');
    }
    n = parseInt(n);
    const result = fib(n);
    res.json({ n, fib: result });
});

app.get('/sleep', (req, res) => {
    let ms = req.query.ms;
    if (!ms || isNaN(ms)){
        return res.status(400).send('Please provide a valid number ms as a query parameter.');
    }
    ms = parseInt(ms);
    setTimeout(() => {
        res.json({ slept_for: ms });
    }, ms);
});

app.get('/cpu', (req, res) => {
    let iterations = req.query.iterations;
    if (!iterations || isNaN(iterations)){
        return res.status(400).send('Please provide a valid number iterations as a query parameter.');
    }
    iterations = parseInt(iterations);
    let count = 0;
    for (let i=0; i<iterations; i++){
        count++;
    }
    res.json({ iterations, count });
});

app.listen(port, () => {
    console.log(`Server is running on http://localhost:${port}`);
});
