# BlueSignal Frontend

React + Vite frontend for the BlueSignal flood response platform.

## 🚀 Quick Start

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Run development server**:
   ```bash
   npm run dev
   ```

   Frontend will be available at `http://localhost:5173`

3. **Build for production**:
   ```bash
   npm run build
   ```

4. **Preview production build**:
   ```bash
   npm run preview
   ```

## 📁 Structure

- `src/`
  - `components/` - Reusable React components
  - `pages/` - Page components (Home, Reports, About)
  - `api/` - API integration with axios
  - `styles/` - CSS modules
  - `utils/` - Helper functions
  - `assets/` - Images and static files

## 🎨 Pages

- **Home** (`/`) - Landing page with dashboard
- **Reports** (`/reports`) - Detailed reports view
- **About** (`/about`) - Project information

## 🔧 Configuration

Edit `vite.config.js` to configure:
- Dev server port
- API proxy
- Build output directory

## 📦 Dependencies

- **react**: UI library
- **react-router-dom**: Routing
- **axios**: HTTP client
- **vite**: Build tool

## 🎨 Styling

This project uses plain CSS (no Tailwind or CSS-in-JS).
All styles are in `src/styles/` directory.

## 🧩 Key Components

- **Navbar**: Main navigation
- **Dashboard**: Real-time reports dashboard
- **ReportCard**: Individual report display
- **Footer**: Site footer

See main README for complete project documentation.

