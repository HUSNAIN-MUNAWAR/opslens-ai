import type { Config } from 'tailwindcss';
export default { content:['./app/**/*.{ts,tsx}','./components/**/*.{ts,tsx}'], theme:{extend:{colors:{canvas:'#111313',panel:'#191c1b',line:'#323733',ink:'#f3f1e9',muted:'#9da39c',signal:'#55c98a',warning:'#e8b25b'}}}, plugins:[] } satisfies Config;
