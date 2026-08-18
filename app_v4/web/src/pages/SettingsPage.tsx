import { useLocation, useRoute } from 'wouter';
import { SettingsServiceSection } from './settings/SettingsServiceSection';
import { SettingsRetentionSection } from './settings/SettingsRetentionSection';
import { SettingsAuthSection } from './settings/SettingsAuthSection';
import { SettingsTimeSection } from './settings/SettingsTimeSection';
import { SettingsAutostartSection } from './settings/SettingsAutostartSection';
import { SettingsLogsSection } from './settings/SettingsLogsSection';
import { SettingsAboutSection } from './settings/SettingsAboutSection';
import { SettingsApiSection } from './settings/SettingsApiSection';

const TABS = [
  { id: 'service', label: 'Service', section: <SettingsServiceSection /> },
  { id: 'retention', label: 'Retention', section: <SettingsRetentionSection /> },
  { id: 'time', label: 'Time / NTP', section: <SettingsTimeSection /> },
  { id: 'autostart', label: 'Auto-start', section: <SettingsAutostartSection /> },
  { id: 'auth', label: 'Authentication', section: <SettingsAuthSection /> },
  { id: 'api', label: 'API', section: <SettingsApiSection /> },
  { id: 'logs', label: 'Logs', section: <SettingsLogsSection /> },
  { id: 'about', label: 'About', section: <SettingsAboutSection /> },
];

export function SettingsPage() {
  const [, setLocation] = useLocation();
  const [, params] = useRoute('/settings/:tab');
  const active = params?.tab ?? 'service';
  const tab = TABS.find((t) => t.id === active) ?? TABS[0];
  return (
    <main className="settings-page">
      <p className="marker">/08 · SETTINGS</p>
      <div className="settings-layout">
        <nav className="settings-tabs">
          {TABS.map((t) => (
            <button key={t.id} data-active={t.id === active} onClick={() => setLocation(`/settings/${t.id}`)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="settings-content">{tab.section}</div>
      </div>
    </main>
  );
}
