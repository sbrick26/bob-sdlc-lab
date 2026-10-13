import { Tag } from '@carbon/react';
import type { Decision } from '../types';

const colors: Record<Decision, 'green' | 'red' | 'purple' | 'gray'> = {
  allowed: 'green',
  blocked: 'red',
  observed: 'purple',
  error: 'gray',
};

export function DecisionTag({ decision }: { decision: Decision }) {
  return <Tag size="sm" type={colors[decision]}>{decision}</Tag>;
}
