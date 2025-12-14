const axios = require("axios");
let jwt;
const email = "";
const password = "";
async function login() {
    const url = "https://api.satsfaucet.com/auth/login";
    const payload = { email, password};
    const response = await axios.post(url, payload);
    console.log(`[LOGIN][${response.status === 200 ? "\x1b[32m200\x1b[0m" : "\x1b[31Error\x1b[0m"}][${response.data.token.slice(0, Math.ceil(response.data.token.length * 0.15)) + "..."}]`);
    jwt = `Bearer ${response.data.token}`;
}

async function bounty() {
    const url = "https://api.satsfaucet.com/app/bounty/claim"
    const time = Date.now();
    const verificationHash = btoa(`ad_watched_${time}_48383`);
    const payload = { adCompleted: true, time, turnstileToken: "test-bypass-token", verificationHash };
    const response = await axios.post(url, payload, { headers: { 'Authorization': jwt, 'Content-Type': 'application/json' } });
    console.log(`[BOUNTY][${response.status === 200 ? "\x1b[32m200\x1b[0m" : "\x1b[31Error\x1b[0m"}/${response.data.success === false ? "\x1b[31mnot ready\x1b[0m" : "\x1b[32mclaimed\x1b[0m"}]`);
}

async function dailyclaim() {
    const url = "https://api.satsfaucet.com/app/daily-reward/claim"
    const response = await axios.post(url, null, { headers: { 'Authorization': jwt, 'Content-Type': 'application/json' } });
    console.log(`[DAILY][${response.status === 200 ? "\x1b[32m200\x1b[0m" : "\x1b[31Error\x1b[0m"}/${response.data.success === false ? "\x1b[31mnot ready\x1b[0m" : "\x1b[32mclaimed\x1b[0m"}]`);

}
async function start() {
    await login();
    await bounty();
    await dailyclaim(); 
    setInterval(bounty, (60 + 1) * 60 * 1000);
    setInterval(dailyclaim, (24 * 60 + 2) * 60 * 1000);
    setInterval(login, (7 * 24 * 60 + 2) * 60 * 1000);
}


start();
