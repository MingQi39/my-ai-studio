import { cn } from '@/components/ui/utils';
import qiLogo from '@/assets/qi-logo.png';

type BrandLogoProps = {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  alt?: string;
};

const sizeClass: Record<NonNullable<BrandLogoProps['size']>, string> = {
  sm: 'w-8 h-8 rounded-lg',
  md: 'w-12 h-12 rounded-xl',
  lg: 'w-20 h-20 rounded-xl',
  xl: 'w-[72px] h-[72px] rounded-xl',
};

export function BrandLogo({ size = 'sm', className, alt = 'Qi' }: BrandLogoProps) {
  return (
    <img
      src={qiLogo}
      alt={alt}
      className={cn(sizeClass[size], 'object-contain', className)}
    />
  );
}
