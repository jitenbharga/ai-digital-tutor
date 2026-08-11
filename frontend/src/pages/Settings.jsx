import { useState } from 'react';
import { usePreferences } from '../context/PreferencesContext';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Check, KeyRound, Copy } from 'lucide-react';
import { api } from '../lib/api';
import MemoryPanel from '../components/MemoryPanel';
import { nudgesEnabled, enableNudges, disableNudges } from '../hooks/useSmartNudges';
import { useTheme } from '../hooks/useTheme';

export default function Settings() {
  const { prefs, updatePrefs, t, flags } = usePreferences();
  const { isDark, toggle: toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [nudges, setNudges] = useState(nudgesEnabled());
  const [inviteCode, setInviteCode] = useState('');
  const [inviteExp, setInviteExp] = useState('');
  const [genLoading, setGenLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [inviteError, setInviteError] = useState('');

  const generateInvite = async () => {
    setGenLoading(true);
    setInviteError('');
    setCopied(false);
    try {
      const res = await api.generateGuardianInvite();
      setInviteCode(res.code);
      setInviteExp(res.expires_in || '24 hours');
    } catch (e) {
      setInviteError(e?.message || 'Could not generate a code. Please try again.');
    } finally {
      setGenLoading(false);
    }
  };

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(inviteCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked — user can select the code manually */ }
  };

  const handleSave = async (patch) => {
    setSaving(true);
    setSaved(false);
    await updatePrefs(patch);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const Option = ({ label, value, current, onChange }) => (
    <button
      onClick={() => onChange(value)}
      className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
        current === value
          ? 'bg-brand-600 text-white shadow-sm'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
    >
      {label}
    </button>
  );

  const Toggle = ({ label, checked, onChange }) => (
    <div className="flex items-center justify-between py-3">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <button
        onClick={() => onChange(!checked)}
        className={`relative w-11 h-6 rounded-full transition-colors ${
          checked ? 'bg-brand-600' : 'bg-gray-300'
        }`}
      >
        <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
          checked ? 'translate-x-5' : ''
        }`} />
      </button>
    </div>
  );

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={20} />
        </button>
        <h2 className="text-xl font-bold text-gray-900">{t('settings')}</h2>
        {saved && (
          <span className="ml-auto flex items-center gap-1 text-green-600 text-sm font-medium">
            <Check size={16} /> {t('saved')}
          </span>
        )}
      </div>

      <div className="space-y-6">
        {/* Language — B5: English, Hindi, Hinglish + regional */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-2">{t('language')}</label>
          <select
            className="input-field w-full"
            value={prefs.language || 'en'}
            onChange={e => handleSave({ language: e.target.value })}
          >
            <option value="en">English</option>
            <option value="hi">हिन्दी (Hindi)</option>
            <option value="hinglish">Hinglish (Hindi-English mix)</option>
            <option value="bn">বাংলা (Bengali)</option>
            <option value="ta">தமிழ் (Tamil)</option>
            <option value="te">తెలుగు (Telugu)</option>
            <option value="mr">मराठी (Marathi)</option>
            <option value="gu">ગુજરાતી (Gujarati)</option>
            <option value="kn">ಕನ್ನಡ (Kannada)</option>
            <option value="ml">മലയാളം (Malayalam)</option>
            <option value="pa">ਪੰਜਾਬੀ (Punjabi)</option>
          </select>
          <p className="text-xs text-gray-400 mt-1">
            Math, code and technical terms stay in English — like your textbook.
          </p>
        </div>

        {/* Reading Level */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-2">{t('reading_level')}</label>
          <div className="flex gap-2">
            <Option label={t('simple')} value="simple" current={prefs.reading_level}
              onChange={v => handleSave({ reading_level: v })} />
            <Option label={t('standard')} value="standard" current={prefs.reading_level}
              onChange={v => handleSave({ reading_level: v })} />
          </div>
        </div>

        {/* Appearance — light / dark mode */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-2">Appearance</label>
          <Toggle label="Dark mode" checked={isDark} onChange={toggleTheme} />
          <p className="text-xs text-gray-400 mt-1">Switch between light and dark. Your choice is remembered on this device.</p>
        </div>

        {/* Font Size */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-2">{t('font_size')}</label>
          <div className="flex gap-2">
            <Option label={t('normal')} value="normal" current={prefs.font_size}
              onChange={v => handleSave({ font_size: v })} />
            <Option label={t('large')} value="large" current={prefs.font_size}
              onChange={v => handleSave({ font_size: v })} />
            <Option label={t('xl')} value="xl" current={prefs.font_size}
              onChange={v => handleSave({ font_size: v })} />
          </div>
        </div>

        {/* TTS / STT toggles — hidden when voice_enabled flag is off (COPPA) */}
        {flags.voice_enabled && (
          <div className="border-t pt-4">
            <Toggle label={t('tts')} checked={prefs.tts_enabled}
              onChange={v => handleSave({ tts_enabled: v })} />
            <Toggle label={t('stt')} checked={prefs.stt_enabled}
              onChange={v => handleSave({ stt_enabled: v })} />
          </div>
        )}

        {/* Daily Reminders */}
        <div className="border-t pt-4">
          <h3 className="text-sm font-semibold text-gray-800 mb-2">{t('reminders') || 'Reminders'}</h3>
          <Toggle label={t('daily_reminder') || 'Daily streak reminder'}
            checked={prefs.daily_reminder || false}
            onChange={async v => {
              handleSave({ daily_reminder: v });
              try { await api.updateReminderSettings({ enabled: v, time: prefs.reminder_time || '09:00' }); } catch {}
            }}
          />
          <p className="text-xs text-gray-400 mt-1">
            {t('reminder_note') || 'A friendly nudge to keep your streak going. You can turn this off anytime.'}
          </p>

          {/* Feature #5: browser study reminders (exam near / reviews due) */}
          <Toggle
            label="Browser study reminders"
            checked={nudges}
            onChange={async v => {
              if (v) {
                const ok = await enableNudges();
                setNudges(ok);
                if (!ok) alert('Allow notifications for this site in your browser to turn on reminders.');
              } else {
                disableNudges();
                setNudges(false);
              }
            }}
          />
          <p className="text-xs text-gray-400 mt-1">
            A gentle browser nudge when an exam is close or reviews are due. Works while the app (or installed PWA) is open.
          </p>
        </div>

        {/* Guardian access — student generates an invite code for a parent/guardian */}
        {flags.guardian_enabled && (
          <div className="border-t pt-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-1">
              <KeyRound size={16} className="text-brand-600" /> Guardian access
            </h3>
            <p className="text-xs text-gray-400 mb-3">
              Generate a code and share it with your parent/guardian. They enter it on their
              Guardian Dashboard to follow your progress (read-only). Expires in 24 hours.
            </p>

            {!inviteCode ? (
              <button
                onClick={generateInvite}
                disabled={genLoading}
                className="px-4 py-2 rounded-xl text-sm font-medium bg-brand-600 text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
              >
                {genLoading ? 'Generating…' : 'Generate invite code'}
              </button>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <code className="flex-1 px-3 py-2 rounded-xl bg-gray-100 text-gray-800 text-sm font-mono select-all break-all">
                    {inviteCode}
                  </code>
                  <button
                    onClick={copyInvite}
                    className="px-3 py-2 rounded-xl text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 flex items-center gap-1 shrink-0"
                  >
                    {copied ? <><Check size={15} /> Copied</> : <><Copy size={15} /> Copy</>}
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  Valid for {inviteExp} · single use.{' '}
                  <button onClick={generateInvite} className="text-brand-600 hover:underline">Generate a new one</button>
                </p>
              </>
            )}
            {inviteError && <p className="text-xs text-red-500 mt-2">{inviteError}</p>}
          </div>
        )}

        {/* A3: Learner memory — transparency & control */}
        <MemoryPanel />
      </div>
    </div>
  );
}
