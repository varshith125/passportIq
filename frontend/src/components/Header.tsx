import React from 'react';
import { ShieldCheck, Cpu } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="app-header" role="banner">
      <div className="app-header__inner">
        <div className="brand-group">
          <div className="brand-mark" aria-hidden="true">
            <ShieldCheck size={22} color="#ffffff" strokeWidth={2.2} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 className="brand-title">PassPortIQ</h1>
              <span className="brand-badge">v2.0</span>
            </div>
            <p className="brand-tagline">
              Intelligent Passport Extraction &amp; ICAO 9303 Verification
            </p>
          </div>
        </div>

        <div className="header-meta">
          <div className="header-pill header-pill--engine" aria-label="OCR Engine">
            <Cpu size={14} className="header-pill__icon" aria-hidden="true" />
            <span>RapidOCR ONNX Runtime · Mod-10 Check Digits</span>
          </div>
          <div className="header-pill header-pill--security" aria-label="Data Privacy">
            <span className="status-dot status-dot--secure" aria-hidden="true" />
            <span>In-Memory Only · Zero Retention</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
