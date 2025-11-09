import express from 'express';
import submitRoutes from './routes/submit';
import jobsRoutes from './routes/jobs';
import feedbackRoutes from './routes/feedback';
import exportRoutes from './routes/export';
import { apiLimiter } from './middlewares/rateLimit';
import { errorHandler } from './middlewares/errorHandler';

const router = express.Router();

router.use(apiLimiter);

router.use('/submit', submitRoutes);
router.use('/jobs', jobsRoutes);
router.use('/feedback', feedbackRoutes);
router.use('/export', exportRoutes);

router.use(errorHandler);

export default router;