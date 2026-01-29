import React, { useEffect, useState } from 'react';
import { I18N } from '../constants';
import { GlassCard } from './VisualEffects';
import { Language, ElectiveCombo } from '../types';
import { assistantApi } from '@/services/api';
import { useAuthStore } from '@/store/authStore';

interface Props {
  lang: Language;
}

const SubjectSelection: React.FC<Props> = ({ lang }) => {
  const [selectedCategory, setSelectedCategory] = useState<'science' | 'humanities' | 'business'>('science');
  const [combos, setCombos] = useState<ElectiveCombo[]>([]);
  const [loadingCombos, setLoadingCombos] = useState(false);
  const [comboError, setComboError] = useState<string | null>(null);
  const { user } = useAuthStore();
  const t = I18N[lang];

  const difficultyStars = (diff: number) => {
    return Array.from({ length: 5 }).map((_, i) => (
      <span key={i} className={i < diff ? 'text-yellow-400' : 'text-gray-300'}>*</span>
    ));
  };

  const parseCombos = (text: string): ElectiveCombo[] => {
    try {
      const parsed = JSON.parse(text);
      if (parsed && Array.isArray(parsed.combos)) {
        return parsed.combos as ElectiveCombo[];
      }
    } catch {
      const match = text.match(/\{[\s\S]*\}/);
      if (match) {
        try {
          const parsed = JSON.parse(match[0]);
          if (parsed && Array.isArray(parsed.combos)) {
            return parsed.combos as ElectiveCombo[];
          }
        } catch {
          return [];
        }
      }
    }
    return [];
  };

  useEffect(() => {
    if (!user?.id) {
      return;
    }
    let active = true;
    setLoadingCombos(true);
    setComboError(null);

    const prompt = `Suggest 3 elective subject combinations for the category "${selectedCategory}".
` +
      `Return JSON only with schema:
` +
      `{"combos":[{"comboId":"id","subjects":["Subject A","Subject B","Subject C"],` +
      `"advantage":"...","suitableMajors":["..."],"difficulty":3}]}
` +
      `Use ${lang === 'en' ? 'English' : 'Traditional Chinese'} labels.`;

    assistantApi.chat({
      student_id: user.id,
      class_id: user.classIds?.[0],
      message: prompt,
      history: [],
    })
      .then((response) => {
        if (!active) return;
        const parsed = parseCombos(response.content);
        if (!parsed.length) {
          setComboError('No recommendations yet.');
        }
        setCombos(parsed);
      })
      .catch((error) => {
        if (!active) return;
        console.error('Failed to load elective combos', error);
        setComboError('Failed to load suggestions.');
        setCombos([]);
      })
      .finally(() => {
        if (active) setLoadingCombos(false);
      });

    return () => {
      active = false;
    };
  }, [selectedCategory, lang, user?.id, user?.classIds]);

  return (
    <div className="space-y-8 animate-fadeIn">
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold">{t.electiveNavigator}</h2>
          <p className="text-gray-500">{t.discoverPath}</p>
        </div>
        <div className="flex bg-gray-100 p-1 rounded-xl">
          {(['science', 'humanities', 'business'] as const).map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                selectedCategory === cat ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {t[cat as keyof typeof t]}
            </button>
          ))}
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {loadingCombos && (
          <div className="col-span-full flex items-center justify-center text-gray-400 text-sm">
            {t.analyzing}
          </div>
        )}
        {!loadingCombos && combos.length === 0 && (
          <div className="col-span-full flex items-center justify-center text-gray-400 text-sm">
            {comboError || (lang === 'en' ? 'No recommendations yet.' : '????')}
          </div>
        )}
        {combos.map((combo) => (
          <GlassCard key={combo.comboId} className="flex flex-col h-full">
            <div className="flex justify-between items-start mb-4">
              <div className="flex gap-2">
                {combo.subjects.map((s) => (
                  <span key={s} className="bg-blue-600 text-white text-[10px] px-2 py-1 rounded uppercase tracking-tighter">
                    {String(s).split(' ')[0]}
                  </span>
                ))}
              </div>
              <div className="text-sm">
                {difficultyStars(combo.difficulty)}
              </div>
            </div>

            <h4 className="text-lg font-bold text-gray-800 mb-2">{combo.advantage}</h4>

            <div className="flex-1 space-y-4">
              <div>
                <p className="text-xs font-bold text-blue-500 uppercase mb-1">{t.suitableMajors}</p>
                <div className="flex flex-wrap gap-2">
                  {combo.suitableMajors.map((m) => (
                    <span key={m} className="text-sm text-gray-600 flex items-center gap-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-400"></div> {m}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <button className="mt-6 w-full py-3 border border-blue-600 text-blue-600 rounded-xl font-medium hover:bg-blue-600 hover:text-white transition-all">
              {t.viewCurriculum}
            </button>
          </GlassCard>
        ))}
      </div>

      <GlassCard className="bg-gradient-to-br from-blue-600 to-cyan-500 text-white border-none relative overflow-hidden">
        <div className="relative z-10 p-4">
          <h3 className="text-xl font-bold mb-2">{t.uniTracker}</h3>
          <p className="opacity-90 mb-6 max-w-lg">{t.uniDesc}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            <div className="bg-white/20 backdrop-blur px-4 py-3 rounded-xl">
              <span className="text-xs uppercase font-bold block mb-1">{t.medSchool}</span>
              <p className="text-sm">{lang === 'en' ? 'Chem (Required), Bio (Preferred)' : '?? (??), ?? (??)'}</p>
            </div>
            <div className="bg-white/20 backdrop-blur px-4 py-3 rounded-xl">
              <span className="text-xs uppercase font-bold block mb-1">{t.engineering}</span>
              <p className="text-sm">{lang === 'en' ? 'Phy / M1/M2 (Highly Preferred)' : '?? / M1/M2 (????)'}</p>
            </div>
            <div className="bg-white/20 backdrop-blur px-4 py-3 rounded-xl">
              <span className="text-xs uppercase font-bold block mb-1">{t.law}</span>
              <p className="text-sm">{lang === 'en' ? 'English L5+, Electives flexible' : '?? L5+, ?????'}</p>
            </div>
          </div>
          <a href="https://www.jupas.edu.hk" target="_blank" rel="noreferrer" className="mt-6 inline-flex items-center text-sm font-bold bg-white text-blue-600 px-6 py-2 rounded-full hover:bg-opacity-90 transition-all">
            {t.openJupas} ?
          </a>
        </div>
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl"></div>
      </GlassCard>
    </div>
  );
};

export default SubjectSelection;
