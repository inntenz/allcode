const fs = require("fs");
const readline = require("readline");
const { google } = require("googleapis");
const axios = require("axios");
const { URL } = require("url");

const CLIENT_ID = "";
const CLIENT_SECRET = "";
const REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob";

const TOKEN_PATH = "./token.json";
const PROCESSED_PATH = "./processed.json";
const CHECK_INTERVAL = 2000;
const ALIAS_EMAIL = "";

const SCOPES = ["https://www.googleapis.com/auth/gmail.modify"];

const oAuth2Client = new google.auth.OAuth2(
  CLIENT_ID,
  CLIENT_SECRET,
  REDIRECT_URI
);

function readProcessed() {
  try {
    if (!fs.existsSync(PROCESSED_PATH)) return new Set();
    const raw = fs.readFileSync(PROCESSED_PATH, "utf8");
    const arr = JSON.parse(raw || "[]");
    return new Set(arr);
  } catch (e) {
    console.error("Error loading processed.json:", e.message);
    return new Set();
  }
}

function saveProcessed(set) {
  try {
    fs.writeFileSync(PROCESSED_PATH, JSON.stringify([...set], null, 2));
  } catch (e) {
    console.error("Error saving processed.json:", e.message);
  }
}

function base64Decode(b64) {
  if (!b64) return "";
  let s = b64.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return Buffer.from(s, "base64").toString("utf8");
}

function decodeHtmlEntities(str) {
  if (!str) return "";
  return str
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function getHtmlFromParts(parts) {
  let html = "";
  if (!parts) return html;
  for (const part of parts) {
    if (part.mimeType === "text/html" && part.body?.data) {
      html += base64Decode(part.body.data);
    } else if (part.parts) {
      html += getHtmlFromParts(part.parts);
    }
  }
  return html;
}

function extractLinksFromHtml(html) {
  const links = [];
  if (!html) return links;
  const regex = /<a[^>]*\s+href=(?:"([^"]+)"|'([^']+)'|([^\s>]+))/g;
  let m;
  while ((m = regex.exec(html)) !== null) {
    const raw = m[1] || m[2] || m[3];
    if (!raw) continue;
    let link = decodeHtmlEntities(raw);
    try {
      const parsed = new URL(link);
      if ((parsed.hostname === "www.google.com" || parsed.hostname === "google.com") && parsed.pathname === "/url") {
        const q = parsed.searchParams.get("q");
        if (q) link = q;
      }
    } catch (e) {}
    links.push(link);
  }
  return links;
}

function authorize() {
  if (fs.existsSync(TOKEN_PATH)) {
    const token = JSON.parse(fs.readFileSync(TOKEN_PATH));
    oAuth2Client.setCredentials(token);
    startListener();
  } else {
    getNewToken();
  }
}

function getNewToken() {
  const authUrl = oAuth2Client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
  });

  console.log("Authorize this app by visiting:\n", authUrl);

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  rl.question("Enter the code here: ", (code) => {
    rl.close();
    oAuth2Client.getToken(code, (err, token) => {
      if (err) return console.error("Token Error:", err);
      oAuth2Client.setCredentials(token);
      fs.writeFileSync(TOKEN_PATH, JSON.stringify(token));
      console.log("Token saved.");
      startListener();
    });
  });
}

async function handleSatsFaucetLink(link) {
  console.log(`Processing SatsFaucet link: ${link}`);
  try {
    const res = await axios.get(link, { maxRedirects: 10, timeout: 15000 });
    console.log("Link called, HTTP status:", res.status);
  } catch (err) {
    if (err.response) {
      console.error("Request error, status:", err.response.status);
    } else {
      console.error("Error calling link:", err.message);
    }
  }
}

function startListener() {
  const gmail = google.gmail({ version: "v1", auth: oAuth2Client });
  console.log("Gmail listener started.");

  const processed = readProcessed();

  setInterval(async () => {
    try {
      const res = await gmail.users.messages.list({
        userId: "me",
        q: `is:unread to:${ALIAS_EMAIL}`,
        maxResults: 50,
      });

      const messages = res.data.messages || [];
      if (messages.length === 0) return;

      console.log(`${messages.length} new mail(s)`);

      for (const msg of messages) {
        const id = msg.id;
        if (processed.has(id)) continue;

        let full;
        try {
          full = await gmail.users.messages.get({ userId: "me", id });
        } catch (e) {
          console.error("Error fetching message:", e.message);
          continue;
        }

        const headers = full.data.payload.headers || [];
        const subject = headers.find(h => h.name === "Subject")?.value || "(no subject)";
        const from = headers.find(h => h.name === "From")?.value || "(unknown)";

        console.log("────────────");
        console.log("From:", from);
        console.log("Subject:", subject);
        console.log("Snippet:", full.data.snippet);

        let htmlBody = "";
        if (full.data.payload.parts) {
          htmlBody = getHtmlFromParts(full.data.payload.parts);
        } else if (full.data.payload.mimeType === "text/html" && full.data.payload.body?.data) {
          htmlBody = base64Decode(full.data.payload.body.data);
        }

        processed.add(id);
        saveProcessed(processed);

        try {
          await gmail.users.messages.modify({
            userId: "me",
            id,
            requestBody: { removeLabelIds: ["UNREAD"] },
          });
        } catch (e) {
          console.error("Error marking as read:", e.message);
        }

        const links = extractLinksFromHtml(htmlBody);
        let satsHandled = false;
        for (const rawLink of links) {
          const link = rawLink.replace(/\s+/g, "");
          if (link.includes("api.satsfaucet.com")) {
            satsHandled = true;
            await handleSatsFaucetLink(link);
            break;
          }
        }

        if (!satsHandled) {
          console.log("No SatsFaucet links found in this message.");
        }
      }
    } catch (err) {
      console.error("Listener error:", err.message);
    }
  }, CHECK_INTERVAL);
}

authorize();
