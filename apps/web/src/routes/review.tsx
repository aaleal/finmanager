import { PageHeader } from '@/components/ui/feedback';
import { ReviewQueue } from '@/components/review-queue';

/**
 * The one cross-module Review Queue.
 *
 * This route is a thin frame: the queue itself is the shared `ReviewQueue`
 * component, so no module ever grows a second one. Confirming here settles the
 * task; «Abrir no módulo» hands the subject to the screen that can actually
 * resolve it — a supermarket receipt opens in the Supermercado review pane,
 * beside its original document (ADR-0025).
 */
export function ReviewPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Fila de revisão"
        description="Vista agregada de todos os módulos. Só chega aqui o que o sistema não conseguiu decidir com confiança suficiente."
      />
      <ReviewQueue />
    </div>
  );
}
