import React, { useState, useContext } from 'react';
import { Wand2, Loader2, Download, PlusCircle } from 'lucide-react';
import { AppContext } from './AppContext';
import { generateImage } from './llmService';
import { ImageSize } from './types';

export default function ImageGenerator() {
  const context = useContext(AppContext);
  const [prompt, setPrompt] = useState('');
  const [size, setSize] = useState<ImageSize>('1K');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setIsGenerating(true);
    setError(null);
    setGeneratedImage(null);

    try {
      const imageUrl = await generateImage(prompt, size);
      setGeneratedImage(imageUrl);
    } catch (err) {
      console.error(err);
      const errorMessage = err instanceof Error ? err.message : "Failed to generate image. Please ensure you have selected a valid paid API key if required.";
      setError(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  const saveToGallery = () => {
    if (!generatedImage || !context) return;
    context.addImageToSession({
      id: crypto.randomUUID(),
      url: generatedImage,
      timestamp: Date.now(),
      name: `ai_gen_${Date.now()}.png`,
    });
    alert("Saved to current session!");
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 p-4 md:p-8 overflow-y-auto">
      <div className="max-w-4xl mx-auto w-full">
        
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-800 mb-2">AI Image Generator</h1>
          <p className="text-slate-600">
            Create high-quality images using the configured OpenRouter model.
            Requires a paid API key.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* Controls */}
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 h-fit">
            <div className="space-y-6">
              
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Prompt</label>
                <textarea 
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe the image you want to create in detail..."
                  className="w-full p-4 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 min-h-[150px] resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Resolution</label>
                <div className="grid grid-cols-3 gap-3">
                  {(['1K', '2K', '4K'] as ImageSize[]).map((s) => (
                    <button
                      key={s}
                      onClick={() => setSize(s)}
                      className={`py-2 px-4 rounded-lg font-medium transition-all ${
                        size === s 
                          ? 'bg-indigo-600 text-white shadow-md' 
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {error && (
                <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm border border-red-100">
                  {error}
                </div>
              )}

              <button
                onClick={handleGenerate}
                disabled={isGenerating || !prompt.trim()}
                className="w-full py-4 bg-indigo-600 text-white rounded-lg font-bold text-lg hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-lg shadow-indigo-200 flex items-center justify-center gap-3"
              >
                {isGenerating ? <Loader2 className="animate-spin" /> : <Wand2 />}
                {isGenerating ? 'Generating...' : 'Generate Image'}
              </button>
            </div>
          </div>

          {/* Preview */}
          <div className="bg-slate-200 rounded-xl border-2 border-dashed border-slate-300 min-h-[400px] flex items-center justify-center relative overflow-hidden group">
            {generatedImage ? (
              <>
                <img 
                  src={generatedImage} 
                  alt="Generated" 
                  className="w-full h-full object-contain bg-slate-800"
                />
                <div className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex justify-center gap-4">
                  <button 
                    onClick={saveToGallery}
                    className="flex items-center gap-2 bg-white text-indigo-900 px-4 py-2 rounded-full font-medium hover:bg-indigo-50 shadow-lg"
                  >
                    <PlusCircle size={18} /> Save to Gallery
                  </button>
                   <a 
                    href={generatedImage} 
                    download={`gen_${Date.now()}.png`}
                    className="flex items-center gap-2 bg-slate-800 text-white px-4 py-2 rounded-full font-medium hover:bg-slate-700 shadow-lg"
                  >
                    <Download size={18} /> Download
                  </a>
                </div>
              </>
            ) : (
              <div className="text-center text-slate-400 p-8">
                {isGenerating ? (
                   <div className="flex flex-col items-center">
                     <Loader2 className="w-12 h-12 animate-spin mb-4 text-indigo-500" />
                     <p>Creating your masterpiece...</p>
                     <p className="text-sm mt-2">This may take a moment.</p>
                   </div>
                ) : (
                  <>
                    <Wand2 className="w-16 h-16 mx-auto mb-4 opacity-50" />
                    <p className="text-lg font-medium">Ready to Generate</p>
                    <p className="text-sm">Enter a prompt and select a size.</p>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
