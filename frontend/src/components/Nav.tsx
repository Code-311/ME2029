import Link from 'next/link';
const links = [
  ['Dashboard', '/dashboard'],
  ['Opportunities', '/opportunities'],
  ['Network', '/network'],
  ['Execution', '/execution'],
  ['Settings', '/settings'],
  ['Admin', '/admin'],
];
export function Nav() {
  return <nav className='flex gap-4 p-4 bg-slate-900 text-white'>{links.map(([l,h]) => <Link key={h} href={h}>{l}</Link>)}</nav>
}
