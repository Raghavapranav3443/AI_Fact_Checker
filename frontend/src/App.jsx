import React from 'react'
import { PipelineProvider, usePipelineContext } from './context/PipelineContext'
import LandingPage  from './pages/LandingPage'
import InputPage    from './pages/InputPage'
import PipelinePage from './pages/PipelinePage'
import ReportPage   from './pages/ReportPage'

function AppInner() {
  const { page } = usePipelineContext()
  return (
    <>
      {page === 'landing'  && <LandingPage />}
      {page === 'input'    && <InputPage />}
      {page === 'pipeline' && <PipelinePage />}
      {page === 'report'   && <ReportPage />}
    </>
  )
}

export default function App() {
  return (
    <PipelineProvider>
      <AppInner />
    </PipelineProvider>
  )
}
