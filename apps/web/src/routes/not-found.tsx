import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/feedback';
import { Compass } from 'lucide-react';

export function NotFoundPage() {
  return (
    <EmptyState
      icon={Compass}
      title="Página não encontrada"
      description="O endereço que seguiu não existe nesta versão da aplicação."
      action={
        <Button asChild variant="outline">
          <Link to="/">Voltar ao painel</Link>
        </Button>
      }
    />
  );
}
