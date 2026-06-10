import { ChevronRight } from 'lucide-react';

/**
 * Сворачиваемая секция на базе нативного <details>.
 *
 * Состояние свёрнутости хранит сам DOM, поэтому при ре-рендере (поллинг и т.п.)
 * пользовательский выбор не сбрасывается. Действия (`actions`) внутри шапки
 * не триггерят toggle — для них перехвачен дефолтный клик.
 */
export default function CollapsibleSection({
  title,
  subtitle,
  actions,
  badge,
  defaultOpen = true,
  level = 'h3',
  children,
}) {
  const Heading = level === 'h2' ? 'h2' : 'h3';
  return (
    <details className="card collapsible-card" open={defaultOpen}>
      <summary className="collapsible-summary">
        <ChevronRight size={18} className="collapsible-chevron" aria-hidden />
        <div className="collapsible-titles">
          <Heading>
            {title}
            {badge != null && <span className="collapsible-badge">{badge}</span>}
          </Heading>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions && (
          <div
            className="collapsible-actions"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
          >
            {actions}
          </div>
        )}
      </summary>
      <div className="collapsible-body">{children}</div>
    </details>
  );
}
