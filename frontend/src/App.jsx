import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { Search, Globe, ChevronRight, Loader2, Send, History } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { CONFIG } from './config';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export default function App() {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [currentResponse, setCurrentResponse] = useState(null);
  const [displayedText, setDisplayedText] = useState('');
  
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [displayedText, isLoading]);

  useEffect(() => {
    if (currentResponse?.answer) {
      let index = 0;
      const text = currentResponse.answer;
      setDisplayedText('');
      
      const interval = setInterval(() => {
        if (index < text.length) {
          setDisplayedText((prev) => prev + text.charAt(index));
          index++;
        } else {
          clearInterval(interval);
        }
      }, CONFIG.UI.TYPING_SPEED);
      
      return () => clearInterval(interval);
    }
  }, [currentResponse]);

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setIsLoading(true);
    setCurrentResponse(null);
    setDisplayedText('');

    try {
      const response = await axios.post(CONFIG.API.ENDPOINT, {
        query: query,
        history: history,
        scrape_top_n: CONFIG.API.SCRAPE_TOP_N
      });

      const { answer, sources } = response.data;
      setCurrentResponse({ query, answer, sources });
      setHistory(prev => [...prev, { role: 'user', content: query }, { role: 'assistant', content: answer }]);
      
    } catch (error) {
      console.error("Search failed:", error);
      setCurrentResponse({
        query,
        answer: "Извините, произошла ошибка. Пожалуйста, попробуйте позже.",
        sources: []
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-[#ededed] flex flex-col items-center">
      
      <main className={cn(
        "w-full max-w-3xl px-6 flex-1 flex flex-col transition-all duration-700 ease-in-out",
        isSearching ? "pt-6" : "justify-center"
      )}>
        
        {/* Brand (Hidden when searching) */}
        {!isSearching && (
          <div className="flex flex-col items-center mb-10 animate-fade-in text-center">
            <div 
              className="w-16 h-16 rounded-full flex items-center justify-center mb-6 alice-glow"
              style={{ backgroundColor: CONFIG.BRAND.ALICE_ICON.BG }}
            >
              <div className="w-0 h-0 border-l-[10px] border-l-transparent border-r-[10px] border-r-transparent border-b-[18px] border-b-white transform -rotate-90 ml-1" />
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-2">{CONFIG.BRAND.NAME}</h1>
            <p className="text-zinc-500 text-lg">{CONFIG.BRAND.SUBTITLE}</p>
          </div>
        )}

        {/* Search Bar */}
        <div className={cn(
          "relative w-full z-10 sticky top-4 mb-6",
          !isSearching && "px-4"
        )}>
          <form 
            onSubmit={handleSearch}
            className="group relative flex items-center bg-[#222] border border-[#333] rounded-3xl p-1.5 focus-within:border-[#444] transition-all"
          >
            <div className="pl-4 pr-2 text-zinc-500">
              <Search className="w-5 h-5" />
            </div>
            <input
              type="text"
              className="flex-1 bg-transparent py-3 pr-4 outline-none text-lg placeholder:text-zinc-600"
              placeholder="Спросите Алису..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
            {query && (
              <button 
                type="submit"
                className="p-3 hover:opacity-90 text-white rounded-full transition-all active:scale-95"
                style={{ backgroundColor: CONFIG.BRAND.ALICE_ICON.BG }}
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ChevronRight className="w-5 h-5" />}
              </button>
            )}
          </form>
        </div>

        {/* Results Area */}
        {isSearching && (
          <div className="flex-1 pb-20 animate-fade-in space-y-6">
            
            {/* Alice Header */}
            <div className="flex items-center gap-3">
              <div 
                className="w-10 h-10 rounded-full flex items-center justify-center alice-glow shrink-0"
                style={{ backgroundColor: CONFIG.BRAND.ALICE_ICON.BG }}
              >
                <div className="w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-b-[12px] border-b-white transform -rotate-90 ml-0.5" />
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-lg leading-tight">Алиса AI</span>
                <span className="text-xs text-zinc-500">Быстрый ответ, возможны неточности</span>
              </div>
            </div>

            {/* Response Content */}
            <div className="space-y-4">
              {isLoading && !displayedText && (
                <div className="space-y-4 animate-pulse pt-4">
                  <div className="h-4 bg-zinc-800 rounded w-3/4"></div>
                  <div className="h-4 bg-zinc-800 rounded w-full"></div>
                </div>
              )}

              <div className="prose max-w-none prose-invert text-xl md:text-2xl font-medium leading-normal text-zinc-100">
                <ReactMarkdown 
                  components={{
                    p: ({children}) => <p className="mb-6 last:mb-0">{children}</p>,
                    strong: ({children}) => <strong className="text-white font-bold">{children}</strong>
                  }}
                >
                  {displayedText}
                </ReactMarkdown>
                
                {/* Sources contextually or at bottom */}
                {!isLoading && currentResponse?.sources && (
                  <div className="flex flex-wrap gap-2 mt-4">
                    {currentResponse.sources.map((source, idx) => (
                      <a 
                        key={idx} 
                        href={source.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="source-badge"
                      >
                        <div className="w-4 h-4 rounded-sm bg-zinc-700 flex items-center justify-center overflow-hidden">
                          <img 
                            src={`https://www.google.com/s2/favicons?domain=${new URL(source.url).hostname}&sz=32`} 
                            alt="" 
                            className="w-3 h-3"
                            onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'block'; }}
                          />
                          <Globe className="w-3 h-3 hidden" />
                        </div>
                        <span>{new URL(source.url).hostname.replace('www.', '')}</span>
                      </a>
                    ))}
                  </div>
                )}

                {isLoading && (
                  <span 
                    className="inline-block w-1 h-6 ml-1 animate-pulse" 
                    style={{ backgroundColor: CONFIG.BRAND.ALICE_ICON.BG }}
                  />
                )}
              </div>
            </div>

            <div ref={scrollRef} />
          </div>
        )}
      </main>

      {/* Footer Navigation */}
      {isSearching && (
        <footer className="fixed bottom-0 w-full p-4 bg-background/90 backdrop-blur-md border-t border-[#222] flex justify-center z-20">
          <button 
            onClick={() => { setIsSearching(false); setQuery(''); setDisplayedText(''); }}
            className="px-6 py-2 bg-[#222] hover:bg-[#2a2a2a] border border-[#333] rounded-full text-sm font-medium transition-colors"
          >
            Новый вопрос
          </button>
        </footer>
      )}
    </div>
  );
}
