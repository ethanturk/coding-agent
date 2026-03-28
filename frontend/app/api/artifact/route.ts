import { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const path = request.nextUrl.searchParams.get('path');
  if (!path) {
    return new Response('Missing path', { status: 400 });
  }

  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const url = `${base}/api/files/artifact?path=${encodeURIComponent(path)}`;
  const res = await fetch(url, { cache: 'no-store' });
  const text = await res.text();
  return new Response(text, {
    status: res.status,
    headers: { 'content-type': 'text/plain; charset=utf-8' },
  });
}
