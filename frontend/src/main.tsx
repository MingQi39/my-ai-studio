import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.tsx';
import './index.css';
import './i18n';
import { refineByIp, bindDocumentLanguage } from './i18n';

bindDocumentLanguage();

// Auto language from IP (skipped if the user already chose a language in the switcher).
refineByIp();

createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
);
