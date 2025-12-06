# Frontend Architecture Documentation

## Overview

The frontend is implemented in React 18+ with Vite build tool and TypeScript. It provides a real-time monitoring dashboard for the airline kit management simulation, visualizing optimization results, inventory levels, costs, and penalties.

## Architecture

### Project Structure

```
frontend/
├── src/
│   ├── App.tsx              # Main app component
│   ├── main.tsx             # Entry point
│   ├── index.css            # Global styles
│   ├── App.css              # App-specific styles
│   ├── components/          # React components
│   │   ├── Dashboard.tsx    # Main dashboard with tabs
│   │   ├── FlightTable.tsx  # Flight decisions table
│   │   ├── InventoryChart.tsx # Inventory visualization
│   │   ├── CostBreakdown.tsx  # Cost analysis charts
│   │   └── PenaltyLog.tsx    # Penalty log table
│   ├── services/            # API communication
│   │   └── api.ts           # Backend API client
│   └── types/               # TypeScript interfaces
│       └── types.ts         # Type definitions
├── index.html               # HTML template
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript configuration
└── package.json             # Dependencies
```

## Components

### Dashboard (`components/Dashboard.tsx`)

Main layout component with:
- **Status display**: Current simulation status, round number, total cost
- **Start button**: Triggers simulation start
- **Tabs**: Switch between monitoring, costs, inventory, penalties views
- **Real-time updates**: Polls backend every 2 seconds

### FlightTable (`components/FlightTable.tsx`)

Displays flight decisions in tabular format:
- Round number and time
- Number of decisions and purchases
- Decision rationale

Shows last 20 decisions (most recent first).

### InventoryChart (`components/InventoryChart.tsx`)

Visualizes inventory levels using Recharts:
- **Bar chart**: Inventory per airport, grouped by class (FIRST, BUSINESS, PREMIUM_ECONOMY, ECONOMY)
- **Responsive**: Adapts to screen size
- **Color-coded**: Different colors per class

### CostBreakdown (`components/CostBreakdown.tsx`)

Cost analysis with two charts:
- **Pie chart**: Total cost breakdown (loading, movement, processing, purchase, penalties)
- **Line chart**: Cost over time (total, operational, penalties)

Uses Recharts for visualization.

### PenaltyLog (`components/PenaltyLog.tsx`)

Penalty tracking:
- **Summary**: Total penalties count and cost
- **Breakdown**: Penalty counts by type
- **Table**: Detailed penalty log with time, code, cost, reason

Shows last 50 penalties (most recent first).

## API Service (`services/api.ts`)

TypeScript wrapper for backend API:
- `getStatus()`: GET /api/status → StatusResponse
- `getInventory()`: GET /api/inventory → InventoryResponse
- `getHistory()`: GET /api/history → HistoryResponse
- `startSimulation(apiKey)`: POST /api/start

Uses Axios for HTTP requests with error handling.

## Type Definitions (`types/types.ts`)

TypeScript interfaces matching backend Pydantic models:
- `ReferenceHour`, `Airport`, `AircraftType`, `Flight`
- `KitLoadDecision`, `KitPurchaseOrder`, `KitMovement`
- `PenaltyRecord`, `GameState`
- `StatusResponse`, `InventoryResponse`, `HistoryResponse`

## Data Flow

1. **Initialization**: App loads, Dashboard component mounts
2. **Polling**: useEffect hook polls backend every 2 seconds
3. **State updates**: React state updates trigger re-renders
4. **User interaction**: Tab switching, start button triggers API calls
5. **Visualization**: Charts update with new data

## Styling

- **CSS Modules**: Component-specific styles in `.css` files
- **Responsive design**: Grid layouts adapt to screen size
- **Modern UI**: Clean, professional design with shadows and transitions
- **Color scheme**: Light theme with accent colors for charts

## Running the Frontend

### Setup

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Starts Vite dev server on `http://localhost:5173`

### Build

```bash
npm run build
```

Creates production bundle in `dist/` folder.

### Preview

```bash
npm run preview
```

Serves production build locally.

## Configuration

### Vite Proxy (`vite.config.ts`)

Proxies `/api` requests to `http://localhost:8000` (backend):
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

### TypeScript (`tsconfig.json`)

- Strict mode enabled
- React JSX transform
- ES2020 target
- Module resolution: bundler

## Dependencies

### Production
- `react`: ^18.2.0
- `react-dom`: ^18.2.0
- `recharts`: ^2.10.3 (chart library)
- `axios`: ^1.6.2 (HTTP client)

### Development
- `@vitejs/plugin-react`: React plugin for Vite
- `typescript`: TypeScript compiler
- `vite`: Build tool

## Real-time Updates

Dashboard polls backend every 2 seconds using `setInterval` in `useEffect`:
- Fetches status, inventory, and history
- Updates React state
- Triggers re-renders of components
- Charts automatically update with new data

## Error Handling

- **API errors**: Displayed in error message banner
- **Loading states**: Button disabled during API calls
- **Empty states**: Friendly messages when no data available
- **Network errors**: Caught and displayed to user

## Performance Considerations

- **Memoization**: `useMemo` hooks prevent unnecessary recalculations
- **Efficient polling**: Only polls when component is mounted
- **Chart optimization**: Recharts handles large datasets efficiently
- **Lazy loading**: Could be added for code splitting if needed

## Future Enhancements

- WebSocket support for real-time updates (no polling)
- Advanced filtering and search
- Export functionality (CSV, PDF)
- Historical data comparison
- Customizable dashboards
- Dark mode support
- Mobile-responsive improvements

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- ES2020+ features required
- No IE11 support

