import { useState } from 'react';
import Dashboard from './components/Dashboard';
import './App.css';

function App() {
  const [apiKey, setApiKey] = useState<string>('');

  return (
    <div className="App">
      <header className="App-header">
        <h1>Airline Kit Management Dashboard</h1>
        <div className="api-key-input">
          <input
            type="password"
            placeholder="Enter API Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && apiKey) {
                // API key will be used when starting simulation
              }
            }}
          />
        </div>
      </header>
      <Dashboard apiKey={apiKey} />
    </div>
  );
}

export default App;

