import { cn } from '@/lib/utils'

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-white/[0.03]", className)}
      {...props}
    />
  )
}

export function GridSkeleton() {
  return (
    <div className="space-y-4 w-full p-4">
      <div className="flex items-center space-x-4 mb-8">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-10 w-24" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-px w-full bg-white/5" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    </div>
  )
}

export function StepSkeleton() {
  return (
    <div className="p-8 space-y-6 max-w-2xl animate-in fade-in slide-in-from-bottom-4 duration-1000">
      <div className="flex items-center gap-4 mb-8">
        <Skeleton className="h-12 w-12 rounded-2xl" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-3 w-32" />
        </div>
      </div>
      
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-start gap-4">
          <Skeleton className="h-6 w-6 rounded-full" />
          <div className="space-y-2 flex-1 pt-1">
            <Skeleton className="h-4 w-full max-w-md" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      ))}
      
      <div className="pt-6 border-t border-white/5">
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
    </div>
  )
}
