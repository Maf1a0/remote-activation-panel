-- =====================================================
-- Remote Activation System Database Setup
-- نظام التحكم عن بُعد - إعداد قاعدة البيانات
-- =====================================================

-- هذا الملف لتوثيق البنية فقط - القاعدة جاهزة ومُعدّة
-- This file is for documentation only - database is already set up

-- إنشاء جدول التفعيلات
-- Create activations table
CREATE TABLE IF NOT EXISTS activations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username text NOT NULL,
  activation_key text NOT NULL,
  activated boolean DEFAULT true,
  expiry timestamptz DEFAULT NULL,
  is_blocked boolean DEFAULT false,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  last_check timestamptz DEFAULT now(),
  device_id text NOT NULL,
  UNIQUE(username, device_id)
);

-- تفعيل Row Level Security
-- Enable Row Level Security
ALTER TABLE activations ENABLE ROW LEVEL SECURITY;

-- سياسات الأمان
-- Security Policies

-- السماح للجميع بإنشاء تفعيل جديد (عند التفعيل الأول)
-- Allow anyone to create new activation (first-time activation)
CREATE POLICY "Anyone can create activation"
  ON activations
  FOR INSERT
  TO anon
  WITH CHECK (true);

-- السماح للجميع بقراءة التفعيلات (للتحقق من الحالة)
-- Allow anyone to read activations (to check status)
CREATE POLICY "Anyone can read activations"
  ON activations
  FOR SELECT
  TO anon
  USING (true);

-- السماح بتحديث وقت آخر فحص
-- Allow updating last check time
CREATE POLICY "Anyone can update their activation check time"
  ON activations
  FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

-- السماح للمدير بإدارة كل شيء
-- Allow admin (service role) to manage everything
CREATE POLICY "Service role can manage all activations"
  ON activations
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- إنشاء فهارس لتسريع البحث
-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_activations_username_device
  ON activations(username, device_id);

CREATE INDEX IF NOT EXISTS idx_activations_activated
  ON activations(activated);

CREATE INDEX IF NOT EXISTS idx_activations_expiry
  ON activations(expiry);

CREATE INDEX IF NOT EXISTS idx_activations_is_blocked
  ON activations(is_blocked);

-- دالة لتحديث updated_at تلقائياً
-- Function to automatically update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- إنشاء Trigger لتحديث updated_at
-- Create trigger for updated_at
DROP TRIGGER IF EXISTS update_activations_updated_at ON activations;
CREATE TRIGGER update_activations_updated_at
  BEFORE UPDATE ON activations
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- بيانات الاتصال
-- Connection Details
-- =====================================================

-- URL: https://dakaxxzbuggkrqncqgrr.supabase.co
-- ANON_KEY: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRha2F4eHpidWdna3JxbmNxZ3JyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk4NTM3NTksImV4cCI6MjA3NTQyOTc1OX0.44XB0eeYyjNqc-xKe8-Feby7ZH7_2HreslosspFSnWM

-- =====================================================
-- ملاحظات مهمة
-- Important Notes
-- =====================================================

-- 1. القاعدة جاهزة ولا تحتاج تشغيل هذا الملف
--    Database is ready - no need to run this file

-- 2. للوصول إلى لوحة التحكم:
--    To access dashboard:
--    https://supabase.com/dashboard

-- 3. للتحكم عبر الويب:
--    For web control:
--    افتح ملف admin_panel.html
--    Open admin_panel.html file

-- 4. للتحكم عبر Python:
--    For Python control:
--    استخدم مكتبة supabase
--    Use supabase library

-- =====================================================
-- أمثلة على الاستعلامات
-- Example Queries
-- =====================================================

-- عرض جميع التفعيلات
-- View all activations
SELECT * FROM activations ORDER BY created_at DESC;

-- عرض التفعيلات النشطة فقط
-- View only active activations
SELECT * FROM activations
WHERE activated = true
  AND is_blocked = false
  AND (expiry IS NULL OR expiry > now())
ORDER BY created_at DESC;

-- عرض التفعيلات المنتهية
-- View expired activations
SELECT * FROM activations
WHERE expiry IS NOT NULL
  AND expiry < now()
ORDER BY expiry DESC;

-- عرض المستخدمين المحظورين
-- View blocked users
SELECT * FROM activations
WHERE is_blocked = true
ORDER BY updated_at DESC;

-- إحصائيات سريعة
-- Quick statistics
SELECT
  COUNT(*) as total_users,
  COUNT(CASE WHEN activated = true AND is_blocked = false THEN 1 END) as active_users,
  COUNT(CASE WHEN is_blocked = true THEN 1 END) as blocked_users,
  COUNT(CASE WHEN expiry IS NOT NULL AND expiry < now() THEN 1 END) as expired_users
FROM activations;

-- =====================================================
-- نهاية الملف
-- End of File
-- =====================================================
