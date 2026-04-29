import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

export default function Markdown({ children, className = '' }) {
  if (!children) return null
  return (
    <div className={`prose-custom ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
