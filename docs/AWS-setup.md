These are the minimal steps for this project to work.

*WARNING:* when setting up the various services and objects below,
it'll make things easier if you stick to the same region/availability zone.
The code in this project uses the `us-east-1` region (N. Virginia) and
the `us-east-1a` availability zone, but yours might be different.
 There are some places currently in the project where these values are hard-coded,
 so you might want to search for those now and replace them.

# IAM
* Create a group with AdministratorAccess policy (a built-in policy),
  say, `admins`.
* Create a user, say, `admin0`:
    * Add the user to the `admins` group.
    * Give the user **programmatic** access.
        * Download the `.csv` credentials file to a secure location, run
        ```shell
        $ chmod 400 <the .csv file>
        ```
        to prevent others from reading its contents.
    * You may also want to give the user the **AWS Management Console**
      (the web interface) access, since you shouldn't use the root user
      much, and you'd want to perform the remaining steps under a
      non-root user.
        * If you do that, make note of the login page link,
        and after you finish with creating the user,
        log out of **AWS Management Console** and log back in under
        the newly created user on the provided login page.

# S3
* Create a bucket,
  say, `s3-bucket`, (it should be a universally unique bucket name),
  so you'll probably need to be more creative.
  Keep it private (i.e., check all "Block public access..." checkboxes).

# VPC
* Create a VPC if one doesn't exist yet, say, `vpc-0`
  (it will have a multiple-digit numeral following the `vpc-` prefix,
  but we're keeping it short, for simplicity)<br/>
  The default VPC will probably have a /16 CIDR block size,
  but if you're creating a new VPC, a /28 size should more than suffice
    * In the associated Security Group, say, `sg-0`,
      add these **inbound** rules:
  
      | Type       | Protocol | Port | Source                      | Description  |
      | ---------- | -------- | ---- | --------------------------- | ------------ |
      | Custom TCP | TPC      | 22   | My IP                       | \<any notes> |
      | Custom TCP | TPC      | 5432 | Custom (use `vpc-0`'s CIDR) | \<any notes> |
      
        * **Custom TCP**, port 22&mdash;This allows
          SSH access from your local machine, you'll need it
        * **Custom TCP**, port 5432
          (unless you change the port when creating an RDS instance)&mdash;This allows
          the instances within your VPC to connect to the RDS database.
          You could also limit this access to a subnet or a specific EC2 instance by
          specifying the corresponding CIDR block
* Create a DynamoDB endpoint
    * In the **Endpoints** tab, click **Create Endpoint**
    * On the next screen:
        * Set **Service Category** to **AWS Services**
        * From the **Service Name** list, select **com.amazonaws.\<your region>.dynamodb**
        * In the **VPC** drop-down, select `vpc-0`
        * Under **Configure route tables**, select the routing table associated with
          the subnets you're using.<br/>
          *NOTE:* If you're setting up the project from scratch,
          there will likely be just one routing table in the list.
          If not, you can go to the EC2 console and double check:
          the routing table should be associated with the subnet in which your EC2 instance
          was created
          (so you may want to defer creating the endpoint
          to after creating the EC2 instance, see below for more on creating the instance).
        * Use the **Full Access** policy
      
        
# EC2
* Create a `t2.micro` instance, say, `i-0`, using the `Ubuntu 18.04 LTS` AMI
  (not minimal). It can be found by searching `ubuntu` and selecting
  **Marketplace** (there will be  few hundred results,
  but this one should pretty close to the top)
    * Add to the existing security group, `sg-0`
    * Create a new key pair for ssh access,
      download the `.pem` key-pair file to a secure location, run
      ```shell
      $ chmod 400 <the .pem file>
      ```
      to prevent others from reading its contents
      (ssh also won't let you use this key pair later on
      if the permissions aren't set to owner-only access)
    * Create an Elastic IP, say, `eipalloc-0`, then associate it
      with the instance `i-0`. When this is done, you can ssh
      to that instance by running
      ```shell
      $ ssh ubuntu@<the elastic IP> -i <the .pem file>
      ```

# The EC2 Instance
* ssh into the instance, and update ubuntu:
  ```shell
  $ sudo apt update
  $ sudo apt upgrade
  ```
* Install python3 and pip3:
  ```shell
  $ sudo apt python3, python3-pip
  ```
* Install `awscli`:
  ```shell
  $ pip3 install --user --upgrade awscli
  ```
  Log out of the instance and log back in for bash to locate `aws`
* You may want to install PostgreSQL CLI to test the instance's
  connection to the RDS later on:
  ```shell
  $ sudo apt install postgresql
  ```
    
# RDS
* Create a PostgreSQL database
    * Choose a name for the database instance and an admin user name
    * Choose `vpc-0` as the **VPC**
    * Choose the **default** Subnet
    * Choose **No** for public accessibility
    * Select **Choose existing VPC security groups**, then select **default**
    * Disable IAM DB authentication
    * Might need to grant RDS Service Linked Role some permissions in IAM
      to let it push logs to Cloud Watch
* After the instance is created, go to instance details and make note
  of the **Endpoint** in the **Connect** section. You'll use it to
  connect to your database.
  If you set up an inbound rule in your security group, `sg-0`,
  as described above, and installed PostgreSQL on your instance, `i-0`,
  you should be able to connect to your database on the database instance
  from `i-0`:
  ```shell
  $ psql -h '<endpoint from the DB`s Connect section>' \
         -p 5432 \
         -U '<DB admin user name>'
  ```
    * If you don't see any messages for a while, your security group's
      inbound rules probably haven't been set up properly
    * When you see the prompt, enter the DB user's password
    * You can also save the password in the `PGPASSWORD` environment
      variable, to avoid typing it in every time
      you connect. Add this line to the end of the `~/.bashrc` file:
      ```shell
      export PGPASSWORD='<DB user`s password>'
      ```
      Then run this from the command line:
      ```shell
      $ source ~/.bashrc
      ```
      
# DynamoDB
* Create a table. For this project, call it `TrafficSpeed`
    * Type in the Primary Key name, `measurementSiteReference`
    (select the **String** type in the drop-down)
    * Check the **Add sorting key** checkbox,
    and type in the Sorting Key name, `measurementTimeDefault` (also **String**)
    * Uncheck the **Use default settings** checkbox, and select the following underneath it:
        * Select **Provisioned** capacity
        * Under **Auto Scaling**, increase the **Minimum provisioned capacity** for
          both reading and writing to 200 units
          (this costs more, but you can update this number later, after the table has been used,
          and you'll have seen how much of the capacity is actually used)
        * For the **IAM Role**, select **DynamoDB AutoScaling Service Linked Role**