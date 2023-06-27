class LinkedinJob:
    def __init__(self, job_name, company_name, company_link, company_size, job_location, job_apply_link,
                 job_description, job_work_type, company_domain):
        self.job_name = job_name
        self.company_name = company_name
        self.company_size = company_size
        self.company_domain = company_domain
        self.company_link = company_link
        self.job_work_type = job_work_type
        self.job_description = job_description
        self.job_apply_link = job_apply_link
        self.job_location = job_location

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self.__dict__)

    def print_csv(self, maintains):
        row = [self.job_name, self.company_name, self.company_size, self.company_domain, self.company_link,
               self.job_work_type, self.job_description, self.job_apply_link, self.job_location]

        writer = maintains.writer
        writer.writerow(row)
