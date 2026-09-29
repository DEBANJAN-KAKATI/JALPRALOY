# Deploying JalProloy to Vercel

JalProloy is configured for seamless deployment on [Vercel](https://vercel.com). The repository supports both **Full-Stack Serverless Deployment** (React + Python FastAPI Serverless Functions) and **Standalone Frontend Deployment** (connecting to a cloud backend).

---

## Architecture on Vercel

```
┌────────────────────────────────────────┐
│             Vercel Edge                │
├───────────────────┬────────────────────┤
│  Frontend (Vite)  │  Serverless Python │
│  React 18 + PWA   │  FastAPI (api/)    │
│  Static CDN       │  Live Hydrometeo   │
└───────────────────┴────────────────────┘
         ▲                   ▲
         │                   │
  Client Browser     Public APIs:
                     - Open-Meteo Weather
                     - GloFAS River API
                     - GDACS Alerts
                     - Google News RSS
                     - Photon OSM Search
```

---

## Method 1: 1-Click Deploy via Vercel CLI (Recommended)

Run the following command from the project root directory:

```bash
npx vercel
```

### Steps:
1. Log in to your Vercel account when prompted in the browser / terminal.
2. Select your scope (account or team).
3. `Link to existing project?` -> **No** (or select existing project if updating).
4. `What's your project's name?` -> **jalproloy**
5. `In which directory is your code located?` -> **`./`** (press Enter)
6. Vercel will detect `vercel.json` and deploy both the React frontend and the Python serverless API functions.

To deploy straight to **Production**:
```bash
npx vercel --prod
```

---

## Method 2: Deploy via GitHub (Vercel Web Dashboard)

1. **Commit and Push your changes to GitHub**:
   ```bash
   git add .
   git commit -m "feat: live data sync, saved places, admin portal, and vercel deployment"
   git push origin main
   ```

2. **Open Vercel Dashboard**:
   - Go to [vercel.com/new](https://vercel.com/new).
   - Click **Import** next to your GitHub repository: `DEBANJAN-KAKATI/JALPRALOY`.

3. **Configure Project**:
   - **Framework Preset**: Other (or Vite)
   - **Root Directory**: `./` (leave default)
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Output Directory**: `frontend/dist`

4. **Environment Variables**:
   Add the following variables in the Vercel dashboard under **Project Settings > Environment Variables**:

   | Variable | Value | Purpose |
   |---|---|---|
   | `DEMO_MODE` | `false` | Enables live hydrometeorological risk inference from Open-Meteo & GloFAS |
   | `CAP_STATUS` | `Exercise` | `Exercise` for prototypes / demos, `Actual` for emergency ops |

5. Click **Deploy**. Vercel will build your frontend and deploy your serverless API routes under `https://your-project.vercel.app/api/*`.

---

## Method 3: Deploy Frontend Only (Connecting to Render / Railway / Cloud Backend)

If you prefer running the heavy Python ML models (such as ConvLSTM and Sentinel-1 pipelines) on an external VM or container host like Render, Railway, or Fly.io:

1. In Vercel, set **Root Directory** to `frontend`.
2. Set the build command to `npm run build` and output directory to `dist`.
3. Set environment variable:
   ```env
   VITE_API_PROXY=https://your-backend-url.onrender.com
   ```
4. All relative `/api/*` calls will proxy directly to your cloud backend.

---

## Verifying Deployment

Once deployed, visit your Vercel URL (e.g., `https://jalproloy.vercel.app`):
1. **Interactive Map**: Hexagons load over Guwahati and Assam with live flood risk.
2. **Live Sync**: Check the green `● LIVE` badge in the header; clicking `⟳ Sync` immediately refreshes Open-Meteo and GloFAS data.
3. **Saved Places**: Add current location or custom Assam localities.
4. **Admin Portal**: View live feed latencies and preview CAP 1.2 XML alerts.
5. **API Endpoints**: Test `https://your-project.vercel.app/api/status` to confirm all feeds report `live`.
