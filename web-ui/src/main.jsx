import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const partnerLogos = {
  unreal: new URL('./assets/partner-logos/unreal-engine.svg', import.meta.url).href,
  blender: new URL('./assets/partner-logos/blender.svg', import.meta.url).href,
};

const initialForm = {
  root: 'G:/ForgeMCP', blender_session: '', blender_object: '',
  destination: '/Game/Content/Returns/', object_name: '', format: 'fbx', replace: false,
};

function Icon({ children }) {
  return <span className="icon" aria-hidden="true">{children}</span>;
}

function PartnerLogo({ app }) {
  return <img className={`partner-logo partner-logo-${app}`} src={partnerLogos[app]} alt="" aria-hidden="true" />;
}

function Glyph({ name }) {
  const paths = {
    bridge: <><path d="M2 13h5l3-8 4 14 3-8h5" /></>,
    project: <><path d="M3 7.5h7l2 2H21v9H3z" /><path d="M3 7.5V6h7l2 2" /></>,
    handoff: <><path d="M3 8h14l-3-3" /><path className="glyph-secondary" d="M21 16H7l3 3" /></>,
    export: <><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5M9 12h7M9 16h7" /></>,
    send: <><path d="M3 12h17M14 6l6 6-6 6" /></>,
    receive: <><path d="M21 12H4m6-6-6 6 6 6" /></>,
    warning: <><path d="M12 3 22 21H2z" /><path d="M12 9v5M12 17h.01" /></>,
  };
  return <svg className={`glyph glyph-${name}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function Card({ title, icon, accent = 'blue', children, className = '' }) {
  return <section className={`card accent-${accent} ${className}`}>
    <h2><Icon>{icon}</Icon><span>{title}</span></h2>{children}
  </section>;
}

function Field({ label, value, placeholder, onChange, className = '', type = 'text' }) {
  return <label className={`field ${className}`}>
    <span>{label}</span>
    <input type={type} value={value ?? ''} placeholder={placeholder} onChange={onChange} />
  </label>;
}

function App() {
  const [live, setLive] = useState({});
  const [form, setForm] = useState(initialForm);
  const [nativeReady, setNativeReady] = useState(false);
  const [actionMessage, setActionMessage] = useState('');
  const initialized = useRef(false);
  // Unreal injects the bound UObject into window.ue. Resolve it at use time:
  // WebBrowser can finish binding after this React tree has first rendered.
  // UE's SWebBrowser lowercases reflected UObject function names in JavaScript.
  const getNative = () => {
    const native = window.ue?.forge;
    return {
      native,
      getState: native?.getstate ?? native?.GetState,
      dispatch: native?.dispatch ?? native?.Dispatch,
    };
  };

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const { native, getState, dispatch } = getNative();
        setNativeReady(Boolean(getState && dispatch));
        if (typeof getState !== 'function') return;
        const result = await getState.call(native);
        const next = typeof result === 'string' ? JSON.parse(result) : result;
        if (!active || !next) return;
        setLive(next);
        if (!initialized.current) {
          initialized.current = true;
          setForm({
            root: next.root ?? initialForm.root,
            blender_session: next.blender_session ?? '',
            blender_object: next.blender_object ?? '',
            destination: next.destination ?? initialForm.destination,
            object_name: next.object_name ?? '',
            format: next.format ?? 'fbx',
            replace: Boolean(next.replace),
          });
        }
      } catch { /* The shell remains usable while the native bridge initializes. */ }
    };
    poll();
    const timer = window.setInterval(poll, 1000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const configure = (next) => {
    setForm(next);
    const { native, dispatch } = getNative();
    if (typeof dispatch === 'function') {
      dispatch.call(native, 'configure', JSON.stringify(next));
      setActionMessage('');
    } else {
      setNativeReady(false);
      setActionMessage('Unreal has not connected this panel to the bridge yet. Reopen the ForgeMCP tab if this persists.');
    }
  };
  const change = (key) => (event) => configure({ ...form, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value });
  const act = (action) => {
    const { native, dispatch } = getNative();
    if (typeof dispatch !== 'function') {
      setNativeReady(false);
      setActionMessage('Unreal has not connected this panel to the bridge yet. Reopen the ForgeMCP tab if this persists.');
      return;
    }
    dispatch.call(native, action, '{}');
    setActionMessage(action === 'start' && live.bridge_running ? 'Bridge is already running.' : '');
  };
  const status = live.transfer_status || 'Select one static mesh asset or actor, then choose a transfer direction.';
  const failed = /failed|error|uncertain|stopped/i.test(status);
  const previewReady = Boolean(live.can_confirm);

  return <main className="shell">
    <header className="masthead">
      <div className="brand"><img src={new URL('./assets/forge-logo.png', import.meta.url)} /><div>
        <div className="brandline"><h1>ForgeMCP</h1><span className="version">{live.version || '0.2.13-alpha.9'}</span></div>
        <p>UNREAL <b>↔</b> BLENDER <i>•</i> MCP BRIDGE</p>
      </div></div>
    </header>

    <Card title="Bridge Status" icon={<Glyph name="bridge" />} accent="blue" className="bridge-card">
      <div className="bridge-grid">
        <div className="bridge-info">
          <div className="status-line"><i className={`status-dot ${live.connected ? 'connected' : live.interrupted ? 'interrupted' : 'offline'}`} /><strong>{live.bridge_running ? 'Bridge running' : 'Bridge stopped'}</strong></div>
          <p className="mono">{live.endpoint || '127.0.0.1:—'} <b>|</b> Session: {live.session_id || 'starting…'}</p>
          <p>{live.connection_text || 'Waiting for the authenticated ForgeMCP client.'}</p>
        </div>
        <div className="bridge-actions">
          <button className="button button-outline" onClick={() => act('start')} disabled={!nativeReady || live.bridge_running}>▶ <span>Start Bridge</span></button>
          <button className="button button-stop" onClick={() => act('stop')} disabled={!nativeReady || !live.bridge_running || live.transfer_busy}>■ <span>Stop Bridge</span></button>
          <small>{actionMessage || (!nativeReady ? 'Connecting this panel to the Unreal bridge…' : 'Automatic authenticated connection starts with the engine, with or without a project open.')}</small>
        </div>
      </div>
    </Card>

    <Card title="Project" icon={<Glyph name="project" />} accent="orange">
      <p className="project-name">{live.project_name || 'Unreal Editor'}</p>
      <p className="muted">Native Blueprint recipes require a reviewed preview.<br />Connection controls do not modify assets.</p>
    </Card>

    <Card title="Unreal ↔ Blender Handoff" icon={<Glyph name="handoff" />} accent="blue">
      <p className="section-subtitle">Unreal / Blender handoff (static mesh FBX or OBJ)</p>
      <Field label="▰　 Handoff Path" value={form.root} onChange={change('root')} />
    </Card>

    <Card title="Blender Connection" icon={<PartnerLogo app="blender" />} accent="orange">
      <Field label="Session ID　ⓘ" value={form.blender_session} placeholder="(blank if only one connected)" onChange={change('blender_session')} />
      <Field label="Blender Object Name　ⓘ" value={form.object_name} placeholder="Leave blank to keep the Unreal source name" onChange={change('object_name')} />
    </Card>

    <Card title="Export Settings" icon={<Glyph name="export" />} accent="blue">
      <label className="field"><span>Export Format</span><select value={form.format} onChange={change('format')}><option value="fbx">FBX</option><option value="obj">OBJ</option></select></label>
    </Card>

    <Card title="Transfer to Blender" icon={<Glyph name="send" />} accent="orange" className="action-card">
      <p className="section-subtitle">Send the selected Unreal static mesh to Blender.</p>
      <button className="button button-primary blue-button" onClick={() => act('send_to_blender')} disabled={live.transfer_busy || !live.connected}><PartnerLogo app="blender" /><span>Send to Blender</span></button>
    </Card>

    <Card title="Transfer to Unreal" icon={<Glyph name="receive" />} accent="orange" className="action-card">
      <Field label="Blender Source Object" value={form.blender_object} placeholder="Blank uses the active Blender mesh" onChange={change('blender_object')} />
      <Field label="Unreal Destination Folder" value={form.destination} onChange={change('destination')} />
      <label className="check-row"><input type="checkbox" checked={form.replace} onChange={change('replace')} /><span>Replace matching bound mesh (verified backup required)</span></label>
      <button className="button button-primary orange-button" onClick={() => act('send_to_unreal')} disabled={live.transfer_busy || !live.connected}><PartnerLogo app="unreal" /><span>Send to Unreal (from Blender)</span></button>
    </Card>

    <Card title="Transfer Status" icon={<Glyph name="warning" />} accent="blue" className="transfer-status-card">
      <div className={`receipt ${failed ? 'receipt-error' : previewReady ? 'receipt-review' : ''}`}>
        <span className="receipt-mark">{failed ? '●' : previewReady ? '◉' : '◌'}</span>
        <div><strong>{live.transfer_busy ? (live.transfer_applying ? 'Transfer in progress' : previewReady ? 'Review transfer preview' : 'Preparing transfer') : failed ? 'Transfer needs attention' : 'Ready'}</strong><p>{status}</p></div>
      </div>
      <div className="status-actions">
        <button className="button button-confirm" disabled={!previewReady} onClick={() => act('confirm')}>✓　 Confirm Transfer</button>
        <button className="button button-cancel" disabled={!live.transfer_busy || live.transfer_applying} onClick={() => act('cancel')}>×　 Cancel Preview</button>
      </div>
    </Card>
    <footer>ForgeMCP alpha · Independent integration for Unreal Engine and Blender · Native transfer preview and confirmation remain enabled</footer>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
