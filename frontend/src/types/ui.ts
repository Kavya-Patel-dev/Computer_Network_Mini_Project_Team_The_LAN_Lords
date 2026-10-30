export type ViewportMode = 'desktop' | 'tablet' | 'mobile'; // 1440, 768, 390
export type UiState = 'normal' | 'loading' | 'empty' | 'error' | 'forbidden';
export type Language = 'en' | 'gu' | 'hi';
export type Theme = 'light' | 'dark';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}
