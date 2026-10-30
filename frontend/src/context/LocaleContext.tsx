import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { Language } from '../types/ui';

interface LocaleContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const TRANSLATIONS: Record<Language, Record<string, string>> = {
  en: {
    dashboard: 'Dashboard',
    myPlans: 'My Plans',
    newPlan: 'New Plan',
    results: 'Results',
    notifications: 'Notifications',
    profile: 'Profile',
    reviewQueue: 'Review Queue',
    allPlans: 'All Plans',
    stats: 'Stats & Analytics',
    users: 'User Management',
    auditLog: 'Audit Log',
    settings: 'Settings',
    permissions: 'Permissions Matrix',
    modelInfo: 'Model Info',
    simulationResult: 'Simulation result',
    honestNotice: 'The AI is an imitation-trained model and does not always win. Evaluated on packet loss and latency.',
    tryDemo: 'Try the Demo',
    login: 'Log In',
    register: 'Register',
    logout: 'Log Out',
    runSimulation: 'Run Simulation',
    packetLoss: 'Packet Loss',
    medianLatency: 'Median Latency',
    p95Latency: 'p95 Latency',
    deliveredThroughput: 'Delivered Throughput',
    congestedSteps: 'Congested Steps (>90%)',
    flowsAtCap: 'Flows at Delay Cap',
    routeFlapping: 'Route Flapping',
    recoverySteps: 'Recovery Steps',
    fallbackRate: 'AI Fallback Rate',
    waitingOtherAdmin: 'Waiting for another admin. You cannot review your own plan.',
  },
  gu: {
    dashboard: 'ડૅશબોર્ડ',
    myPlans: 'મારી યોજનાઓ',
    newPlan: 'નવી યોજના',
    results: 'પરિણામો',
    notifications: 'સૂચનાઓ',
    profile: 'પ્રોફાઇલ',
    reviewQueue: 'સમીક્ષા કતાર',
    allPlans: 'બધી યોજનાઓ',
    stats: 'આંકડા અને વિશ્લેષણ',
    users: 'વપરાશકર્તા સંચાલન',
    auditLog: 'ઓડિટ લોગ',
    settings: 'સેટિંગ્સ',
    permissions: 'પરવાનગીઓ',
    modelInfo: 'મોડલ માહિતી',
    simulationResult: 'સિમ્યુલેશન પરિણામ',
    honestNotice: 'AI હંમેશા જીતતું નથી. તે પેકેટ નુકશાન અને વિલંબ પર મૂલ્યાંકન કરે છે.',
    tryDemo: 'ડેમો અજમાવો',
    login: 'લૉગ ઇન',
    register: 'નોંધણી કરો',
    logout: 'લૉગ આઉટ',
    runSimulation: 'સિમ્યુલેશન ચલાવો',
    packetLoss: 'પેકેટ લોસ',
    medianLatency: 'મધ્યસ્થ લેટન્સી',
    p95Latency: 'p95 લેટન્સી',
    deliveredThroughput: 'થ્રુપુટ',
    congestedSteps: 'ભીડવાળા પગલાં (>90%)',
    flowsAtCap: 'મર્યાદા પર પ્રવાહ',
    routeFlapping: 'રૂટ ફ્લૅપિંગ',
    recoverySteps: 'રિકવરી પગલાં',
    fallbackRate: 'AI ફૉલબૅક દર',
    waitingOtherAdmin: 'અન્ય એડમિનની રાહ જોઈ રહ્યું છે. તમે તમારી યોજનાની સમીક્ષા કરી શકતા નથી.',
  },
  hi: {
    dashboard: 'डैशबोर्ड',
    myPlans: 'मेरी योजनाएं',
    newPlan: 'नई योजना',
    results: 'परिणाम',
    notifications: 'सूचनाएं',
    profile: 'प्रोफाइल',
    reviewQueue: 'समीक्षा कतार',
    allPlans: 'सभी योजनाएं',
    stats: 'सांख्यिकी और विश्लेषण',
    users: 'उपयोगकर्ता प्रबंधन',
    auditLog: 'ऑडिट लॉग',
    settings: 'सेटिंग्स',
    permissions: 'अनुमतियां',
    modelInfo: 'मॉडल जानकारी',
    simulationResult: 'सिमुलेशन परिणाम',
    honestNotice: 'एआई हमेशा बेहतर नहीं होता। इसका मूल्यांकन पैकेट लॉस और लेटेंसी पर किया जाता है।',
    tryDemo: 'डेमो आज़माएं',
    login: 'लॉग इन',
    register: 'पंजीकरण करें',
    logout: 'लॉग आउट',
    runSimulation: 'सिमुलेशन चलाएं',
    packetLoss: 'पैकेट लॉस',
    medianLatency: 'मध्यिका लेटेंसी',
    p95Latency: 'p95 लेटेंसी',
    deliveredThroughput: 'डिलीवर थ्रूपुट',
    congestedSteps: 'भीड़भाड़ वाले चरण (>90%)',
    flowsAtCap: 'विलंब सीमा पर प्रवाह',
    routeFlapping: 'रूट फ्लैपिंग',
    recoverySteps: 'रिकवरी चरण',
    fallbackRate: 'एआई फॉलबैक दर',
    waitingOtherAdmin: 'अन्य व्यवस्थापक की प्रतीक्षा है। आप अपनी योजना की समीक्षा नहीं कर सकते।',
  },
};

const LocaleContext = createContext<LocaleContextType | undefined>(undefined);

export const LocaleProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [language, setLanguage] = useState<Language>('en');

  useEffect(() => {
    const body = document.body;
    body.classList.remove('lang-gu', 'lang-hi');
    if (language === 'gu') {
      body.classList.add('lang-gu');
    } else if (language === 'hi') {
      body.classList.add('lang-hi');
    }
  }, [language]);

  const t = (key: string): string => {
    return TRANSLATIONS[language]?.[key] || TRANSLATIONS.en[key] || key;
  };

  return (
    <LocaleContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LocaleContext.Provider>
  );
};

export const useLocale = () => {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error('useLocale must be used within a LocaleProvider');
  }
  return context;
};
