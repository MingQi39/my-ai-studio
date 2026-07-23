import { createRoot } from 'react-dom/client';
import { BrowserRouter, HashRouter } from 'react-router-dom';
import App from './App.tsx';
import './index.css';
import './i18n';
import { refineByIp, bindDocumentLanguage } from './i18n';
import { isElectronRuntime } from './platform';

bindDocumentLanguage();

// Auto language from IP (skipped if the user already chose a language in the switcher).
refineByIp();

const Router = isElectronRuntime() ? HashRouter : BrowserRouter;

createRoot(document.getElementById('root')!).render(
  <Router>
    <App />
  </Router>,
);
