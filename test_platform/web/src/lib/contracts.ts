export interface ReviewFinding {
  risk_level: 'H' | 'M' | 'L'
  category: '逻辑缺陷' | '安全隐患' | '易用性建议'
  description: string
  suggestion: string
  source_quote?: string
}

export interface RoleReport {
  label: string
  content: string
}

export interface ReviewRunPayload {
  reports: Record<string, RoleReport>
  findings: ReviewFinding[]
  markdown?: string
}

export interface TestCaseStep {
  action: string
  expected: string
}

export type TestCasePriority = 'P0' | 'P1' | 'P2' | 'P3'

export interface TestCaseItem {
  id: string
  priority: TestCasePriority
  module: string
  title: string
  precondition?: string
  tags?: string
  remark?: string
  steps: TestCaseStep[]
}

export interface TestCaseModule {
  name: string
  path: string
  cases: TestCaseItem[]
  children: TestCaseModule[]
}

export interface TestCaseSuite {
  items: TestCaseItem[]
  modules?: TestCaseModule[]
  summary: string
  markdown?: string
}

export interface TestCaseReviewFinding {
  risk_level: 'H' | 'M' | 'L'
  category: string
  related_case_ids: string[]
  related_requirement_points: string[]
  description: string
  suggestion: string
}

export interface TestCaseReviewItem {
  case_id: string
  title: string
  module: string
  verdict: 'pass' | 'warning' | 'fail'
  consistency: 'aligned' | 'partial' | 'deviated'
  issues: string[]
  suggestions: string[]
}

export interface TestCaseReviewPayload {
  summary: string
  findings: TestCaseReviewFinding[]
  reviewed_cases: TestCaseReviewItem[]
  revised_suite: TestCaseSuite
  markdown?: string
}

export interface RequirementAnalysisItem {
  module: string
  summary?: string
  actors: string[]
  business_rules: string[]
  data_entities: string[]
  preconditions?: string[]
  postconditions?: string[]
  exceptions?: string[]
  risks?: string[]
  open_questions?: string[]
}

export interface RequirementAnalysisPack {
  items: RequirementAnalysisItem[]
  summary: string
  markdown?: string
}

export interface FlowchartItem {
  module: string
  title: string
  summary?: string
  mermaid: string
  warnings?: string[]
}

export interface FlowchartPack {
  items: FlowchartItem[]
  summary: string
  markdown?: string
}

export interface TestDataTableResult {
  title: string
  fieldSummaryMarkdown: string
  selectSql: string
  insertSql: string
  updateSql: string
  deleteSql: string
}

export interface TestDataScenarioResult {
  title: string
  dependencyMarkdown: string
  selectSql: string
  insertSql: string
  updateSql: string
  deleteSql: string
}

export interface TestDataMetric {
  label: string
  value: string
}

export interface TestDataPack {
  documentName?: string
  summaryMarkdown: string
  metrics: TestDataMetric[]
  tableListMarkdown: string
  scenarioListMarkdown: string
  tables: TestDataTableResult[]
  scenarios: TestDataScenarioResult[]
  warningsMarkdown: string
  markdown: string
  sqlFileContent: string
}

export interface ApiTestSpecServer {
  url: string
  description?: string
}

export interface ApiTestAuthProfile {
  required_headers: string[]
  required_cookies: string[]
}

export interface ApiTestResource {
  resource_key: string
  tag?: string
  lookup_fields: string[]
  operation_ids: string[]
  operation_categories?: string[]
}

export interface ApiTestOperation {
  operation_id: string
  summary?: string
  category: string
  resource_key?: string
}

export interface ApiTestSpec {
  title: string
  version?: string
  openapi_version?: string
  servers: ApiTestSpecServer[]
  auth_profile: ApiTestAuthProfile
  resources: ApiTestResource[]
  operations: ApiTestOperation[]
  warnings?: string[]
}

export interface ApiTestExtractRule {
  name?: string
  from?: string
  pick: string
}

export interface ApiTestCase {
  case_id: string
  title: string
  operation_id: string
  resource_key?: string
  category: string
  priority: TestCasePriority
  depends_on: string[]
  extract?: ApiTestExtractRule[]
  assertions?: string[]
}

export interface ApiTestScene {
  scene_id: string
  title: string
  description?: string
  steps: string[]
}

export interface ApiTestSceneOrder {
  scene_id: string
  ordered_steps: string[]
}

export interface ApiTestLinkPlan {
  ordered_case_ids: string[]
  standalone_case_ids: string[]
  scene_orders: ApiTestSceneOrder[]
  case_dependencies?: Record<string, string[]>
  extract_variables?: Record<string, string[]>
  warnings?: string[]
}

export interface ApiTestSuiteMeta {
  suite_id?: string
  suite_version?: number
  title?: string
  case_count?: number
  scene_count?: number
  storage_path?: string
}

export interface ApiTestReportFailureCase {
  key: string
  title: string
  detail: string
  kind: string
}

export interface ApiTestReportArtifact {
  key: string
  label: string
  value: string
}

export interface ApiTestReport {
  status?: string
  headline?: string
  summary_lines?: string[]
  failure_cases?: ApiTestReportFailureCase[]
  artifact_labels?: ApiTestReportArtifact[]
}

export interface ApiTestHistorySummary {
  spec_title?: string
  suite_id?: string
  suite_version?: number
  status?: string
  case_count?: number
  scene_count?: number
  report_headline?: string
  stats?: ApiTestExecutionStats
  pass_rate?: number | null
}

export interface ApiTestExecutionStats {
  total: number
  passed: number
  failed: number
  errors: number
  skipped: number
}

export interface ApiTestExecutionArtifacts {
  run_dir?: string
  generated_script?: string
  compiled_script?: string
  junit_xml?: string
  runtime_config?: string
  asset_snapshot?: string
  case_snapshot?: string
  scene_snapshot?: string
  execution_summary?: string
  allure_results?: string
  allure_archive?: string
}

export interface ApiTestExecutionResult {
  run_id?: string
  status?: string
  summary?: string
  stats?: ApiTestExecutionStats
  command?: string
  stdout?: string
  stderr?: string
  junit_xml_content?: string
  execution_summary_content?: string
  runtime_config_content?: string
  asset_snapshot_content?: string
  case_snapshot_content?: string
  scene_snapshot_content?: string
  artifacts?: ApiTestExecutionArtifacts
}

export interface ApiTestPack {
  summary: string
  spec: ApiTestSpec
  cases: ApiTestCase[]
  scenes: ApiTestScene[]
  script?: string
  execution?: ApiTestExecutionResult
  link_plan?: ApiTestLinkPlan
  suite?: ApiTestSuiteMeta
  report?: ApiTestReport
  markdown?: string
}

export interface DashboardMetric {
  label: string
  value: string
  delta: string
  color: string
  bg: string
  border: string
}

export interface DashboardActivity {
  id: number | string
  action: string
  target: string
  timestamp: string
  status: 'success' | 'running' | 'fail'
  icon: string
}

export interface DashboardStats {
  metrics: DashboardMetric[]
  recent_activities: DashboardActivity[]
}

export interface HistoryReportSummary {
  id: string
  timestamp?: string
  filename?: string
  type: string
  meta?: {
    api_test_summary?: ApiTestHistorySummary
    [key: string]: unknown
  }
}

export interface HistoryReportDetail extends HistoryReportSummary {
  content: string
  meta: Record<string, unknown>
}
